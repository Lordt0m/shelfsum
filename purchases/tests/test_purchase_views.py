from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
from catalogue.models import Product
from inventory.models import StockMovement
from purchases.models import Purchase, PurchaseLine
from purchases.services import complete_purchase


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PurchaseViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        self.staff = get_user_model().objects.create_user(
            email="staff@example.com", password="password"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )
        self.client.force_login(self.owner)

    def product(self, **overrides):
        values = {"business": self.business, "name": "Golden Penny", "sku": "GP-1"}
        values.update(overrides)
        return Product.objects.create(**values)

    def purchase_data(self, *lines, **overrides):
        values = {
            "purchase_date": "2026-09-09",
            "supplier_name": "Ada Supplies",
            "reference": "INV-101",
            "notes": "Delivered this morning.",
            "lines-TOTAL_FORMS": str(max(3, len(lines))),
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
        }
        for index in range(max(3, len(lines))):
            prefix = f"lines-{index}"
            if index < len(lines):
                product, quantity, unit_cost = lines[index]
                values.update(
                    {
                        f"{prefix}-product": str(product.pk),
                        f"{prefix}-quantity": str(quantity),
                        f"{prefix}-unit_cost": str(unit_cost),
                    }
                )
            else:
                values.update(
                    {
                        f"{prefix}-product": "",
                        f"{prefix}-quantity": "",
                        f"{prefix}-unit_cost": "",
                    }
                )
        values.update(overrides)
        return values

    def draft(self, *lines, creator=None, **overrides):
        purchase = Purchase.objects.create(
            business=self.business,
            creator=creator or self.owner,
            purchase_date=overrides.get("purchase_date", date(2026, 9, 9)),
            supplier_name=overrides.get("supplier_name", "Ada Supplies"),
        )
        for product, quantity, unit_cost in lines:
            PurchaseLine.objects.create(
                purchase=purchase,
                product=product,
                quantity=quantity,
                unit_cost=Decimal(unit_cost),
            )
        return purchase

    def purchase_edit_data(self, purchase, *lines):
        data = self.purchase_data(*lines)
        existing_lines = list(purchase.lines.order_by("pk"))
        data["lines-TOTAL_FORMS"] = str(max(3, len(existing_lines)))
        data["lines-INITIAL_FORMS"] = str(len(existing_lines))
        for index, line in enumerate(existing_lines):
            data[f"lines-{index}-id"] = str(line.pk)
        return data

    def test_owner_can_create_edit_and_complete_a_multi_line_draft_without_javascript(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")

        create = self.client.post(
            reverse("purchase_create"),
            self.purchase_data((first, 3, "101.25"), (second, 4, "202.50")),
        )

        purchase = Purchase.objects.get()
        self.assertRedirects(create, reverse("purchase_detail", args=[purchase.pk]))
        form_page = self.client.get(reverse("purchase_edit", args=[purchase.pk]))
        self.assertContains(form_page, 'name="lines-0-product"')
        self.assertContains(form_page, "Remove this line")
        self.assertContains(form_page, "Save draft")

        edit = self.client.post(
            reverse("purchase_edit", args=[purchase.pk]),
            self.purchase_edit_data(
                purchase, (first, 5, "111.00"), (second, 4, "202.50")
            ),
        )
        self.assertRedirects(edit, reverse("purchase_detail", args=[purchase.pk]))
        complete = self.client.post(reverse("purchase_detail", args=[purchase.pk]))
        self.assertRedirects(complete, reverse("purchase_detail", args=[purchase.pk]))
        detail = self.client.get(complete.url)
        self.assertContains(detail, "Completed")
        self.assertContains(detail, "Total: 1365.00")
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.Status.COMPLETED)

    def test_server_rendered_add_line_round_trip_preserves_draft_values_without_javascript(self):
        product = self.product()

        response = self.client.post(
            reverse("purchase_create"),
            self.purchase_data((product, 3, "10.00"), add_line="1"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="lines-TOTAL_FORMS" value="4"')
        self.assertContains(response, 'name="lines-0-product"')
        self.assertContains(response, "Document total")
        self.assertFalse(Purchase.objects.exists())

    def test_server_rendered_remove_checkbox_deletes_a_draft_line_without_javascript(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")
        purchase = self.draft((first, 1, "10.00"), (second, 2, "20.00"))
        data = self.purchase_edit_data(
            purchase, (first, 1, "10.00"), (second, 2, "20.00")
        )
        data["lines-1-DELETE"] = "on"

        response = self.client.post(reverse("purchase_edit", args=[purchase.pk]), data)

        self.assertRedirects(response, reverse("purchase_detail", args=[purchase.pk]))
        self.assertEqual(purchase.lines.count(), 1)
        self.assertEqual(purchase.lines.get().product, first)

    def test_active_staff_can_create_edit_and_complete_purchase(self):
        product = self.product()
        self.client.force_login(self.staff)
        create = self.client.post(
            reverse("purchase_create"), self.purchase_data((product, 2, "20.00"))
        )
        purchase = Purchase.objects.get()
        self.assertRedirects(create, reverse("purchase_detail", args=[purchase.pk]))
        edit = self.client.post(
            reverse("purchase_edit", args=[purchase.pk]),
            self.purchase_edit_data(purchase, (product, 3, "25.00")),
        )
        self.assertRedirects(edit, reverse("purchase_detail", args=[purchase.pk]))
        complete = self.client.post(reverse("purchase_detail", args=[purchase.pk]))
        self.assertRedirects(complete, reverse("purchase_detail", args=[purchase.pk]))
        product.refresh_from_db()
        self.assertEqual(product.stock_on_hand, 3)
        self.assertEqual(product.unit_cost, Decimal("25.00"))

    def test_blank_duplicate_invalid_inactive_and_cross_business_lines_have_clear_errors(self):
        product = self.product()
        blank = self.client.post(reverse("purchase_create"), self.purchase_data())
        duplicate = self.client.post(
            reverse("purchase_create"),
            self.purchase_data((product, 1, "10.00"), (product, 2, "11.00")),
        )
        invalid = self.client.post(
            reverse("purchase_create"), self.purchase_data((product, 0, "-1.00"))
        )
        product.is_active = False
        product.save(update_fields=["is_active"])
        inactive = self.client.post(
            reverse("purchase_create"), self.purchase_data((product, 1, "10.00"))
        )
        other_business = Business.objects.create(name="Other Shop")
        hidden = Product.objects.create(
            business=other_business, name="Hidden", sku="HIDDEN-1"
        )
        cross_business = self.client.post(
            reverse("purchase_create"), self.purchase_data((hidden, 1, "10.00"))
        )

        self.assertContains(blank, "Add at least one Product line.")
        self.assertContains(duplicate, "A Product can appear only once on a Purchase.")
        self.assertContains(invalid, "Quantity must be a positive whole number.")
        self.assertContains(invalid, "Ensure this value is greater than or equal to 0.")
        self.assertContains(inactive, "Select a valid choice")
        self.assertContains(cross_business, "Select a valid choice")
        self.assertFalse(Purchase.objects.exists())

    def test_list_detail_and_edit_are_business_scoped_and_filters_are_retained(self):
        visible_product = self.product()
        visible = self.draft((visible_product, 1, "10.00"))
        complete_purchase(business=self.business, actor=self.owner, purchase=visible)
        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        hidden = Purchase.objects.create(
            business=other_business,
            creator=other_owner,
            purchase_date=date(2026, 9, 9),
        )

        listing = self.client.get(
            reverse("purchase_list"),
            {"status": "completed", "date_from": "2026-09-01", "date_to": "2026-09-30"},
        )
        self.assertContains(listing, f"Purchase #{visible.pk}")
        self.assertNotContains(listing, f"Purchase #{hidden.pk}")
        self.assertContains(listing, 'value="completed" selected')
        self.assertContains(listing, 'value="2026-09-01"')
        invalid_date = self.client.get(reverse("purchase_list"), {"date_from": "nope"})
        self.assertContains(invalid_date, "Enter a valid start date.")
        for response in (
            self.client.get(reverse("purchase_detail", args=[hidden.pk])),
            self.client.post(reverse("purchase_edit", args=[hidden.pk]), self.purchase_data()),
        ):
            self.assertEqual(response.status_code, 404)

    def test_demo_and_inactive_members_are_denied_at_request_boundary(self):
        product = self.product()
        draft = self.draft((product, 1, "10.00"))
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        for response in (
            self.client.post(reverse("purchase_create"), self.purchase_data((product, 1, "10.00"))),
            self.client.post(reverse("purchase_edit", args=[draft.pk]), self.purchase_data((product, 2, "11.00"))),
            self.client.post(reverse("purchase_detail", args=[draft.pk])),
        ):
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, "Demo Business is read-only", status_code=403)
        self.assertEqual(StockMovement.objects.count(), 0)

        self.business.is_demo = False
        self.business.save(update_fields=["is_demo"])
        membership = Membership.objects.get(user=self.staff, business=self.business)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        self.client.force_login(self.staff)
        for response in (
            self.client.get(reverse("purchase_list")),
            self.client.get(reverse("purchase_detail", args=[draft.pk])),
            self.client.post(reverse("purchase_create"), self.purchase_data((product, 1, "10.00"))),
            self.client.post(reverse("purchase_edit", args=[draft.pk]), self.purchase_data((product, 2, "11.00"))),
            self.client.post(reverse("purchase_detail", args=[draft.pk])),
        ):
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, "access is inactive", status_code=403)

    def test_completed_purchase_cannot_be_edited_or_completed_again_at_request_boundary(self):
        product = self.product()
        purchase = self.draft((product, 2, "10.00"))
        complete = self.client.post(reverse("purchase_detail", args=[purchase.pk]))
        self.assertRedirects(complete, reverse("purchase_detail", args=[purchase.pk]))

        edit = self.client.post(
            reverse("purchase_edit", args=[purchase.pk]),
            self.purchase_edit_data(purchase, (product, 4, "20.00")),
        )
        repeated = self.client.post(reverse("purchase_detail", args=[purchase.pk]))
        self.assertRedirects(edit, reverse("purchase_detail", args=[purchase.pk]))
        self.assertEqual(repeated.status_code, 400)
        self.assertContains(repeated, "already been completed", status_code=400)
        product.refresh_from_db()
        self.assertEqual(product.stock_on_hand, 2)
        self.assertEqual(StockMovement.objects.count(), 1)
