from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
from catalogue.models import Product
from catalogue.services import ProductCreation, create_product


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ProductViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        self.client.force_login(self.owner)

    def product_data(self, **overrides):
        data = {
            "name": "Golden Penny Spaghetti",
            "sku": "GP-SPAG-500",
            "description": "500 g pack",
            "selling_price": "1250.00",
            "unit_cost": "1080.50",
            "opening_quantity": "12",
            "low_stock_threshold": "3",
        }
        data.update(overrides)
        return data

    def create_existing_product(self, **overrides):
        values = {
            "name": "Golden Penny Spaghetti",
            "sku": "GP-SPAG-500",
            "description": "500 g pack",
            "selling_price": Decimal("1250.00"),
            "unit_cost": Decimal("1080.50"),
            "opening_quantity": 12,
            "low_stock_threshold": 3,
        }
        values.update(overrides)
        return create_product(
            business=self.business,
            actor=self.owner,
            details=ProductCreation(**values),
        )

    def test_owner_can_create_product_and_see_its_stock_trace(self):
        response = self.client.post(reverse("product_create"), self.product_data())

        product = Product.objects.get()
        self.assertRedirects(response, reverse("product_detail", args=[product.pk]))
        detail = self.client.get(response.url)
        self.assertContains(detail, "12 units")
        self.assertContains(detail, "Opening stock")
        self.assertNotContains(detail, 'name="stock_on_hand"')

    def test_invalid_and_duplicate_identifiers_return_useful_errors(self):
        self.create_existing_product()

        response = self.client.post(
            reverse("product_create"),
            self.product_data(
                name="golden penny spaghetti",
                sku="gp-spag-500",
                selling_price="-1.00",
                unit_cost="-2.00",
                opening_quantity="-1",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertContains(response, "cannot be negative")
        self.assertEqual(Product.objects.count(), 1)

    def test_crafted_stock_on_hand_field_cannot_bypass_opening_quantity(self):
        response = self.client.post(
            reverse("product_create"),
            self.product_data(opening_quantity="0", stock_on_hand="999"),
        )

        product = Product.objects.get()
        self.assertRedirects(response, reverse("product_detail", args=[product.pk]))
        self.assertEqual(product.stock_on_hand, 0)

    def test_product_pages_are_scoped_to_the_current_business(self):
        visible = self.create_existing_product()
        other_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        other_business = Business.objects.create(name="Other Shop")
        Membership.objects.create(
            user=other_owner,
            business=other_business,
            role=Membership.Role.OWNER,
        )
        hidden = Product.objects.create(
            business=other_business,
            name=visible.name,
            sku=visible.sku,
        )

        list_response = self.client.get(reverse("product_list"))
        detail_response = self.client.get(reverse("product_detail", args=[hidden.pk]))

        self.assertContains(list_response, visible.name)
        self.assertNotContains(list_response, other_business.name)
        self.assertEqual(detail_response.status_code, 404)

        edit_response = self.client.post(
            reverse("product_edit", args=[hidden.pk]), self.product_data(name="Intrusion")
        )
        deactivate_response = self.client.post(
            reverse("product_deactivate", args=[hidden.pk])
        )
        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(deactivate_response.status_code, 404)

    def test_demo_business_rejects_product_creation(self):
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])

        response = self.client.post(reverse("product_create"), self.product_data())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Product.objects.exists())

    def test_permitted_fields_can_be_edited_without_changing_stock(self):
        product = self.create_existing_product()
        movement_count = product.stock_movements.count()

        response = self.client.post(
            reverse("product_edit", args=[product.pk]),
            {
                "name": "Golden Penny Pasta",
                "sku": "GP-PASTA-500",
                "description": "Updated description",
                "selling_price": "1300.00",
                "unit_cost": "1100.00",
                "low_stock_threshold": "5",
                "stock_on_hand": "999",
            },
        )

        self.assertRedirects(response, reverse("product_detail", args=[product.pk]))
        product.refresh_from_db()
        self.assertEqual(product.name, "Golden Penny Pasta")
        self.assertEqual(product.stock_on_hand, 12)
        self.assertEqual(product.stock_movements.count(), movement_count)

    def test_price_can_change_while_name_and_sku_stay_the_same(self):
        product = self.create_existing_product()

        response = self.client.post(
            reverse("product_edit", args=[product.pk]),
            {
                "name": product.name,
                "sku": product.sku,
                "description": product.description,
                "selling_price": "1400.00",
                "unit_cost": product.unit_cost,
                "low_stock_threshold": product.low_stock_threshold,
            },
        )

        self.assertRedirects(response, reverse("product_detail", args=[product.pk]))
        product.refresh_from_db()
        self.assertEqual(product.selling_price, Decimal("1400.00"))

    def test_deactivation_preserves_history_and_excludes_stock_activity_choices(self):
        product = self.create_existing_product()

        response = self.client.post(reverse("product_deactivate", args=[product.pk]))

        self.assertRedirects(response, reverse("product_detail", args=[product.pk]))
        product.refresh_from_db()
        self.assertFalse(product.is_active)
        self.assertEqual(product.stock_movements.count(), 1)
        other_business = Business.objects.create(name="Other Choice Shop")
        Product.objects.create(business=other_business, name="Other Active Product")
        choices = Product.objects.available_for_stock_activity(business=self.business)
        self.assertFalse(choices.exists())

    def test_search_and_filters_are_combined_within_the_current_business(self):
        low = self.create_existing_product(
            name="Peak Milk", sku="PEAK-01", opening_quantity=3, low_stock_threshold=3
        )
        high = self.create_existing_product(
            name="Milo Refill", sku="MILO-02", opening_quantity=8, low_stock_threshold=2
        )
        high.is_active = False
        high.save(update_fields=["is_active"])
        other_owner = get_user_model().objects.create_user(
            email="other-filter@example.com", password="password"
        )
        other_business = Business.objects.create(name="Other Filter Shop")
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        Product.objects.create(business=other_business, name="Peak Hidden", sku="PEAK-X")

        response = self.client.get(
            reverse("product_list"), {"q": "peak", "status": "active", "stock": "low"}
        )

        self.assertContains(response, low.name)
        self.assertNotContains(response, high.name)
        self.assertNotContains(response, "Peak Hidden")
        self.assertContains(response, 'value="peak"')
        self.assertContains(response, "Low stock")

    def test_inactive_filter_and_no_result_state_are_clear(self):
        product = self.create_existing_product()
        product.is_active = False
        product.save(update_fields=["is_active"])

        inactive = self.client.get(reverse("product_list"), {"status": "inactive"})
        missing = self.client.get(reverse("product_list"), {"q": "does-not-exist"})

        self.assertContains(inactive, product.name)
        self.assertContains(inactive, "Inactive")
        self.assertContains(missing, "No Products match these filters")

    def test_low_stock_filter_has_a_specific_empty_state(self):
        self.create_existing_product(opening_quantity=8, low_stock_threshold=2)

        response = self.client.get(reverse("product_list"), {"stock": "low"})

        self.assertContains(response, "No Products match the low-stock filter")

    def test_demo_business_rejects_product_edit_and_deactivation(self):
        product = self.create_existing_product()
        initial_events = self.business.audit_events.count()
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])

        edit_response = self.client.post(
            reverse("product_edit", args=[product.pk]),
            self.product_data(name="Changed Demo Product"),
        )
        deactivate_response = self.client.post(
            reverse("product_deactivate", args=[product.pk])
        )

        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(deactivate_response.status_code, 403)
        product.refresh_from_db()
        self.assertEqual(product.name, "Golden Penny Spaghetti")
        self.assertTrue(product.is_active)
        self.assertEqual(self.business.audit_events.count(), initial_events)
