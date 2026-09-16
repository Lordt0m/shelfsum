from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from catalogue.models import Product
from purchases.forms import PurchaseForm, PurchaseLineFormSet
from purchases.models import Purchase, PurchaseLine
from purchases.services import create_draft_purchase


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PurchaseDraftCreationServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        self.other_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        self.other_business = Business.objects.create(name="Other Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.other_owner,
            business=self.other_business,
            role=Membership.Role.OWNER,
        )

    def product(self, business=None, **overrides):
        values = {
            "business": business or self.business,
            "name": "Golden Penny",
            "sku": "GP-1",
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def forms(self, product, *, form_instance=None, formset_instance=None):
        data = {
            "purchase_date": "2026-09-09",
            "supplier_name": "Ada Supplies",
            "reference": "INV-101",
            "notes": "Delivered this morning.",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(product.pk),
            "lines-0-quantity": "2",
            "lines-0-unit_cost": "10.00",
        }
        form = PurchaseForm(data, instance=form_instance or Purchase())
        formset = PurchaseLineFormSet(
            data,
            instance=formset_instance or Purchase(),
            form_kwargs={"business": self.business},
        )
        if product.business_id != self.business.pk:
            formset.forms[0].fields["product"].queryset = Product.objects.all()
        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())
        return form, formset

    def test_create_assigns_explicit_business_and_actor(self):
        product = self.product()
        forged = Purchase(
            business=self.other_business,
            creator=self.other_owner,
            purchase_date=date(2020, 1, 1),
        )
        form, formset = self.forms(
            product, form_instance=forged, formset_instance=forged
        )

        purchase = create_draft_purchase(
            business=self.business,
            actor=self.owner,
            form=form,
            formset=formset,
        )

        self.assertEqual(purchase.business_id, self.business.pk)
        self.assertEqual(purchase.creator_id, self.owner.pk)
        self.assertEqual(purchase.status, Purchase.Status.DRAFT)
        self.assertEqual(
            list(purchase.lines.values_list("product_id", "quantity", "unit_cost")),
            [(product.pk, 2, Decimal("10.00"))],
        )
        self.assertFalse(AuditEvent.objects.filter(business=self.business).exists())

    def test_demo_and_inactive_actor_are_denied_at_service_boundary(self):
        product = self.product()
        form, formset = self.forms(product)
        with self.assertRaises(PermissionDenied):
            create_draft_purchase(
                business=self.business,
                actor=self.other_owner,
                form=form,
                formset=formset,
            )
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        with self.assertRaises(PermissionDenied):
            create_draft_purchase(
                business=self.business,
                actor=self.owner,
                form=form,
                formset=formset,
            )

        self.business.is_demo = False
        self.business.save(update_fields=["is_demo"])
        membership = Membership.objects.get(user=self.owner)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            create_draft_purchase(
                business=self.business,
                actor=self.owner,
                form=form,
                formset=formset,
            )

    def test_foreign_product_is_rejected_even_when_form_queryset_allows_it(self):
        foreign = self.product(
            business=self.other_business, name="Foreign", sku="FOREIGN-1"
        )
        form, formset = self.forms(foreign)
        formset.forms[0].fields["product"].queryset = Product.objects.all()
        self.assertTrue(formset.is_valid())

        with self.assertRaisesRegex(ValidationError, "must belong to this Business"):
            create_draft_purchase(
                business=self.business,
                actor=self.owner,
                form=form,
                formset=formset,
            )
        self.assertFalse(Purchase.objects.exists())

    def test_requires_one_non_deleted_line(self):
        product = self.product()
        form, formset = self.forms(product)
        formset.forms[0].cleaned_data["DELETE"] = True

        with self.assertRaisesRegex(ValidationError, "at least one Product line"):
            create_draft_purchase(
                business=self.business,
                actor=self.owner,
                form=form,
                formset=formset,
            )
        self.assertFalse(Purchase.objects.exists())

    def test_parent_and_lines_roll_back_when_line_persistence_fails(self):
        product = self.product()
        form, formset = self.forms(product)
        with patch.object(
            PurchaseLine,
            "save",
            side_effect=RuntimeError("line persistence failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "line persistence failure"):
                create_draft_purchase(
                    business=self.business,
                    actor=self.owner,
                    form=form,
                    formset=formset,
                )

        self.assertFalse(Purchase.objects.exists())
        self.assertFalse(PurchaseLine.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
