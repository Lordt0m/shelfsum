from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from businesses.models import Business, Membership
from auditing.models import AuditEvent
from .models import Expense
from .services import correct_expense, record_expense, void_expense

@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ExpenseRequestTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="Strong-pass-123")
        self.staff = User.objects.create_user(email="staff@example.com", password="Strong-pass-123")
        self.business = Business.objects.create(name="Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.staff, business=self.business, role=Membership.Role.STAFF)
        self.client.force_login(self.owner)

    def payload(self, **extra):
        return {"date": "2026-09-01", "category": "rent", "description": "Premises", "amount": "125.40", "notes": "Monthly", **extra}

    def test_owner_and_staff_can_record_and_list_decimal_expense(self):
        response = self.client.post(reverse("expense_create"), self.payload())
        expense = Expense.objects.get()
        self.assertRedirects(response, reverse("expense_detail", kwargs={"expense_id": expense.pk}))
        self.assertEqual(expense.amount, Decimal("125.40"))
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("expense_list")), "Premises")

    def test_staff_can_record_an_expense(self):
        self.client.force_login(self.staff)

        response = self.client.post(reverse("expense_create"), self.payload())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Expense.objects.get().actor, self.staff)

    def test_create_rejects_invalid_money_and_categories(self):
        invalid_money = self.client.post(
            reverse("expense_create"), self.payload(amount="0")
        )
        invalid_precision = self.client.post(
            reverse("expense_create"), self.payload(amount="125.405")
        )
        invalid_category = self.client.post(
            reverse("expense_create"), self.payload(category="payroll")
        )

        self.assertEqual(invalid_money.status_code, 200)
        self.assertEqual(invalid_precision.status_code, 200)
        self.assertEqual(invalid_category.status_code, 200)
        self.assertEqual(Expense.objects.count(), 0)

    def test_create_rejects_voided_status_without_writing(self):
        with self.assertRaises(ValidationError):
            Expense.objects.create(
                business=self.business,
                actor=self.owner,
                status=Expense.Status.VOIDED,
                **self.payload(),
            )
        self.assertEqual(Expense.objects.count(), 0)

    def test_list_filters_dates_and_status_without_leaking_other_business(self):
        recorded = Expense.objects.create(
            business=self.business,
            actor=self.owner,
            date=date(2026, 9, 1),
            category=Expense.Category.RENT,
            description="September rent",
            amount=Decimal("125.40"),
        )
        voided = Expense.objects.create(
            business=self.business,
            actor=self.owner,
            date=date(2026, 9, 15),
            category=Expense.Category.UTILITIES,
            description="September utilities",
            amount=Decimal("25.40"),
        )
        void_expense(business=self.business, actor=self.owner, expense=voided)
        other = Business.objects.create(name="Other shop")
        Expense.objects.create(
            business=other,
            actor=self.owner,
            date=date(2026, 9, 15),
            category=Expense.Category.RENT,
            description="Hidden rent",
            amount=Decimal("50.00"),
        )

        response = self.client.get(
            reverse("expense_list"),
            {"status": Expense.Status.VOIDED, "date_from": "2026-09-10", "date_to": "2026-09-20"},
        )

        self.assertContains(response, voided.description)
        self.assertNotContains(response, recorded.description)
        self.assertNotContains(response, "Hidden rent")
        invalid_date = self.client.get(reverse("expense_list"), {"date_from": "not-a-date"})
        self.assertContains(invalid_date, "Enter a valid start date.")

    def test_impossible_calendar_filter_dates_show_validation_instead_of_failing(self):
        for field in ("date_from", "date_to"):
            with self.subTest(field=field):
                response = self.client.get(
                    reverse("expense_list"), {field: "2026-13-01"}
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Enter a valid")

    def test_mutating_routes_scope_ids_and_deny_inactive_or_demo_members(self):
        expense = Expense.objects.create(
            business=self.business,
            actor=self.owner,
            date=date(2026, 9, 1),
            category=Expense.Category.RENT,
            description="Premises",
            amount=Decimal("125.40"),
        )
        other = Business.objects.create(name="Other shop")
        hidden = Expense.objects.create(
            business=other,
            actor=self.owner,
            date=date(2026, 9, 1),
            category=Expense.Category.RENT,
            description="Hidden",
            amount=Decimal("125.40"),
        )
        self.assertEqual(
            self.client.post(reverse("expense_void", args=[hidden.pk])).status_code,
            404,
        )
        membership = Membership.objects.get(user=self.staff, business=self.business)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse("expense_create"), self.payload()).status_code, 403)
        self.assertEqual(self.client.post(reverse("expense_void", args=[expense.pk])).status_code, 403)
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse("expense_create"), self.payload()).status_code, 403)
        self.assertEqual(self.client.post(reverse("expense_correct", args=[expense.pk]), self.payload()).status_code, 403)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.RECORDED)

    def test_void_and_create_are_post_only_and_require_csrf(self):
        expense = Expense.objects.create(
            business=self.business,
            actor=self.owner,
            date=date(2026, 9, 1),
            category=Expense.Category.RENT,
            description="Premises",
            amount=Decimal("125.40"),
        )
        self.assertEqual(self.client.get(reverse("expense_void", args=[expense.pk])).status_code, 405)
        self.assertEqual(Expense.objects.filter(pk=expense.pk, status=Expense.Status.RECORDED).count(), 1)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        csrf_client.get(reverse("expense_create"))
        self.assertEqual(csrf_client.post(reverse("expense_create"), self.payload()).status_code, 403)
        token = csrf_client.cookies["csrftoken"].value
        self.assertEqual(
            csrf_client.post(
                reverse("expense_create"), self.payload(), HTTP_X_CSRFTOKEN=token
            ).status_code,
            302,
        )

    def test_correction_voids_original_once_and_preserves_lineage(self):
        original = Expense.objects.create(business=self.business, actor=self.owner, date=date(2026, 9, 1), category="rent", description="Premises", amount=Decimal("125.40"))
        response = self.client.post(reverse("expense_correct", kwargs={"expense_id": original.pk}), self.payload(amount="130.00"))
        replacement = Expense.objects.get(correction_of=original)
        original.refresh_from_db()
        self.assertRedirects(response, reverse("expense_detail", kwargs={"expense_id": replacement.pk}))
        self.assertEqual(original.status, Expense.Status.VOIDED)
        self.assertEqual(replacement.amount, Decimal("130.00"))
        self.assertEqual(AuditEvent.objects.filter(business=self.business).count(), 1)
        self.assertContains(
            self.client.get(reverse("expense_detail", args=[original.pk])),
            f"Replaced by Expense #{replacement.pk}",
        )
        self.assertEqual(self.client.post(reverse("expense_correct", kwargs={"expense_id": original.pk}), self.payload()).status_code, 400)

    def test_void_returns_the_voided_expense_for_following_callers(self):
        expense = Expense.objects.create(
            business=self.business,
            actor=self.owner,
            date=date(2026, 9, 1),
            category=Expense.Category.RENT,
            description="Premises",
            amount=Decimal("125.40"),
        )

        returned = void_expense(
            business=self.business, actor=self.owner, expense=expense
        )

        self.assertEqual(returned.status, Expense.Status.VOIDED)

    def test_direct_correction_requires_the_origin_business_to_match(self):
        original = Expense.objects.create(
            business=self.business,
            actor=self.owner,
            date=date(2026, 9, 1),
            category=Expense.Category.RENT,
            description="Premises",
            amount=Decimal("125.40"),
        )
        other_business = Business.objects.create(name="Other shop")

        forged = Expense(
            business=other_business,
            actor=self.owner,
            correction_of=original,
            date=date(2026, 9, 2),
            category=Expense.Category.RENT,
            description="Forged replacement",
            amount=Decimal("130.00"),
        )

        with self.assertRaises(ValidationError):
            forged.full_clean()

    def test_direct_replacement_requires_a_persisted_voided_origin(self):
        original = Expense.objects.create(
            business=self.business,
            actor=self.owner,
            date=date(2026, 9, 1),
            category=Expense.Category.RENT,
            description="Premises",
            amount=Decimal("125.40"),
        )
        forged_origin = Expense(
            pk=original.pk,
            business=self.business,
            status=Expense.Status.VOIDED,
        )
        forged = Expense(
            business=self.business,
            actor=self.owner,
            correction_of=forged_origin,
            date=date(2026, 9, 2),
            category=Expense.Category.RENT,
            description="Forged replacement",
            amount=Decimal("130.00"),
        )

        with self.assertRaisesRegex(ValidationError, "voided original"):
            forged.full_clean()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ExpenseServiceInvariantTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        self.business = Business.objects.create(name="Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )

    def details(self, **overrides):
        values = {
            "date": date(2026, 9, 1),
            "category": Expense.Category.RENT,
            "description": "Premises",
            "amount": Decimal("125.40"),
            "notes": "Monthly",
        }
        values.update(overrides)
        return values

    def expense(self):
        return Expense.objects.create(
            business=self.business, actor=self.owner, **self.details()
        )

    def test_services_reject_cross_business_and_demo_writes(self):
        expense = self.expense()
        other = Business.objects.create(name="Other")
        with self.assertRaisesRegex(ValidationError, "does not belong"):
            void_expense(business=other, actor=self.owner, expense=expense)
        with self.assertRaisesRegex(ValidationError, "does not belong"):
            correct_expense(
                business=other, actor=self.owner, expense=expense, details=self.details()
            )
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        with self.assertRaises(PermissionDenied):
            record_expense(
                business=self.business, actor=self.owner, details=self.details()
            )

    def test_audit_database_failure_rolls_back_record_void_and_correction(self):
        operations = (
            (
                "record",
                lambda expense: record_expense(
                    business=self.business, actor=self.owner, details=self.details()
                ),
                None,
            ),
            (
                "void",
                lambda expense: void_expense(
                    business=self.business, actor=self.owner, expense=expense
                ),
                Expense.Status.RECORDED,
            ),
            (
                "correct",
                lambda expense: correct_expense(
                    business=self.business,
                    actor=self.owner,
                    expense=expense,
                    details=self.details(amount=Decimal("130.00")),
                ),
                Expense.Status.RECORDED,
            ),
        )
        for label, operation, expected_status in operations:
            with self.subTest(operation=label):
                expense = self.expense() if expected_status else None
                count_before = Expense.objects.count()
                with patch(
                    "auditing.models.AuditEvent.objects.create",
                    side_effect=RuntimeError("database write failed"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "database write failed"):
                        operation(expense)
                self.assertEqual(Expense.objects.count(), count_before)
                if expense is not None:
                    expense.refresh_from_db()
                    self.assertEqual(expense.status, expected_status)
                    self.assertFalse(Expense.objects.filter(correction_of=expense).exists())
                self.assertEqual(AuditEvent.objects.count(), 0)

    def test_immutable_expenses_reject_instance_bulk_and_expression_bypasses(self):
        expense = self.expense()
        expense.description = "Changed"
        with self.assertRaises(TypeError):
            expense.save()
        with self.assertRaises(TypeError):
            Expense.objects.filter(pk=expense.pk).update(description="Changed")
        with self.assertRaises(TypeError):
            Expense.objects.filter(pk=expense.pk).update(amount=F("amount"))
        with self.assertRaises(TypeError):
            Expense.objects.filter(pk=expense.pk).update(status=F("status"))
        expense.description = "Changed"
        with self.assertRaises(TypeError):
            Expense.objects.bulk_update([expense], ["description"])

    def test_correction_lineage_rejects_self_and_duplicate_replacements(self):
        original = self.expense()
        with self.assertRaisesRegex(ValidationError, "cannot correct itself"):
            Expense(
                pk=original.pk,
                business=self.business,
                actor=self.owner,
                correction_of=original,
                **self.details(description="Self correction"),
            ).full_clean()
        replacement = correct_expense(
            business=self.business,
            actor=self.owner,
            expense=original,
            details=self.details(amount=Decimal("130.00")),
        )
        duplicate = Expense(
            business=self.business,
            actor=self.owner,
            correction_of=original,
            **self.details(description="Duplicate correction"),
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        self.assertEqual(replacement.correction_of_id, original.pk)

    def test_bulk_create_validates_generator_expenses_and_lineage(self):
        original = self.expense()
        invalid = Expense(
            business=self.business,
            actor=self.owner,
            correction_of=original,
            **self.details(description="Unvoided replacement"),
        )
        with self.assertRaisesRegex(ValidationError, "voided original"):
            Expense.objects.bulk_create(expense for expense in [invalid])
        self.assertEqual(Expense.objects.count(), 1)
