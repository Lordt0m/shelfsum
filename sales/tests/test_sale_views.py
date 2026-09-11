from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
from catalogue.models import Product
from sales.models import Sale, SaleLine


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SaleViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="owner@example.com", password="password")
        self.staff = get_user_model().objects.create_user(email="staff@example.com", password="password")
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.staff, business=self.business, role=Membership.Role.STAFF)
        self.client.force_login(self.owner)

    def product(self, **overrides):
        values = {"business": self.business, "name": "Golden Penny", "sku": "GP-1", "stock_on_hand": 5, "unit_cost": Decimal("4.00"), "selling_price": Decimal("10.00")}
        values.update(overrides)
        return Product.objects.create(**values)

    def sale_data(self, *lines, **overrides):
        values = {"sale_date": "2026-09-09", "customer_name": "Walk-in customer", "reference": "SALE-1", "notes": "Counter sale", "lines-TOTAL_FORMS": str(max(3, len(lines))), "lines-INITIAL_FORMS": "0", "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "1000"}
        for index in range(max(3, len(lines))):
            prefix = f"lines-{index}"
            if index < len(lines):
                product, quantity, unit_price = lines[index]
                values.update({f"{prefix}-product": str(product.pk), f"{prefix}-quantity": str(quantity), f"{prefix}-unit_price": str(unit_price)})
            else: values.update({f"{prefix}-product": "", f"{prefix}-quantity": "", f"{prefix}-unit_price": ""})
        values.update(overrides)
        return values

    def test_owner_staff_can_create_complete_and_no_js_add_line(self):
        product = self.product(); second = self.product(name="Milo", sku="MILO-1", stock_on_hand=4)
        response = self.client.post(reverse("sale_create"), self.sale_data((product, 2, "10.00"), (second, 1, "20.00")))
        sale = Sale.objects.get(); self.assertRedirects(response, reverse("sale_detail", args=[sale.pk]))
        self.assertContains(self.client.get(reverse("sale_edit", args=[sale.pk])), "Save draft")
        complete = self.client.post(reverse("sale_detail", args=[sale.pk])); self.assertRedirects(complete, reverse("sale_detail", args=[sale.pk]))
        self.assertContains(self.client.get(complete.url), "Cost snapshot")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("sale_create"), self.sale_data((product, 1, "11.00"), add_line="1"))
        self.assertEqual(response.status_code, 200); self.assertContains(response, 'name="lines-TOTAL_FORMS" value="4"')
        response = self.client.post(reverse("sale_create"), self.sale_data((product, 1, "11.00")))
        staff_sale = Sale.objects.latest("pk")
        self.assertRedirects(response, reverse("sale_detail", args=[staff_sale.pk]))
        self.assertRedirects(self.client.post(reverse("sale_detail", args=[staff_sale.pk])), reverse("sale_detail", args=[staff_sale.pk]))
        staff_sale.refresh_from_db()
        self.assertEqual(staff_sale.status, Sale.Status.COMPLETED)

    def test_invalid_duplicate_empty_inactive_and_oversell_errors(self):
        product = self.product(stock_on_hand=1)
        self.assertContains(self.client.post(reverse("sale_create"), self.sale_data()), "Add at least one Product line.")
        self.assertContains(self.client.post(reverse("sale_create"), self.sale_data((product, 1, "10"), (product, 1, "11"))), "A Product can appear only once on a Sale.")
        self.assertContains(self.client.post(reverse("sale_create"), self.sale_data((product, 0, "10"))), "Quantity must be a positive whole number.")
        sale = Sale.objects.create(business=self.business, creator=self.owner, sale_date=date(2026, 9, 9)); SaleLine.objects.create(sale=sale, product=product, quantity=2, unit_price=Decimal("10"))
        response = self.client.post(reverse("sale_detail", args=[sale.pk])); self.assertContains(response, "available Stock on Hand", status_code=400)
        inactive = self.product(name="Inactive", sku="INACTIVE")
        inactive.is_active = False; inactive.save(update_fields=["is_active"])
        self.assertContains(self.client.post(reverse("sale_create"), self.sale_data((inactive, 1, "10"))), "Select a valid choice.")

    def test_demo_inactive_and_cross_business_post_requests_are_denied(self):
        product = self.product()
        self.business.is_demo = True; self.business.save(update_fields=["is_demo"])
        self.assertEqual(self.client.post(reverse("sale_create"), self.sale_data((product, 1, "10"))).status_code, 403)
        self.business.is_demo = False; self.business.save(update_fields=["is_demo"])
        membership = Membership.objects.get(user=self.owner, business=self.business)
        membership.is_active = False; membership.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(reverse("sale_create"), self.sale_data((product, 1, "10"))).status_code, 403)
        membership.is_active = True; membership.save(update_fields=["is_active"])
        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(email="other@example.com", password="password")
        Membership.objects.create(user=other_owner, business=other_business, role=Membership.Role.OWNER)
        other_product = Product.objects.create(business=other_business, name="Other", sku="OTHER")
        hidden = Sale.objects.create(business=other_business, creator=other_owner, sale_date=date(2026, 9, 9))
        SaleLine.objects.create(sale=hidden, product=other_product, quantity=1, unit_price=Decimal("10"))
        self.assertEqual(self.client.post(reverse("sale_detail", args=[hidden.pk])).status_code, 404)

    def test_list_filters_and_business_isolation(self):
        product = self.product(); sale = Sale.objects.create(business=self.business, creator=self.owner, sale_date=date(2026, 9, 9)); SaleLine.objects.create(sale=sale, product=product, quantity=1, unit_price=Decimal("10"))
        other_business = Business.objects.create(name="Other Shop"); other_owner = get_user_model().objects.create_user(email="other@example.com", password="password"); Membership.objects.create(user=other_owner, business=other_business, role=Membership.Role.OWNER)
        hidden = Sale.objects.create(business=other_business, creator=other_owner, sale_date=date(2026, 9, 9))
        response = self.client.get(reverse("sale_list"), {"status": "draft", "date_from": "2026-09-01", "date_to": "2026-09-30"})
        self.assertContains(response, f"Sale #{sale.pk}"); self.assertNotContains(response, f"Sale #{hidden.pk}"); self.assertContains(response, 'value="draft" selected')
        self.assertEqual(self.client.get(reverse("sale_detail", args=[hidden.pk])).status_code, 404)
