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

    def test_demo_business_rejects_product_creation(self):
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])

        response = self.client.post(reverse("product_create"), self.product_data())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Product.objects.exists())
