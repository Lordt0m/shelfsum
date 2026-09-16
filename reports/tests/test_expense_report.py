import csv
from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
from expenses.models import Expense
from expenses.services import correct_expense, void_expense


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ExpenseReportRequestTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="owner@example.com", password="password"
        )
        self.staff = user_model.objects.create_user(
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

    def expense(self, *, expense_date, amount="10.00", description="Premises"):
        return Expense.objects.create(
            business=self.business,
            actor=self.owner,
            date=expense_date,
            category=Expense.Category.RENT,
            description=description,
            amount=Decimal(amount),
        )

    def test_recorded_report_includes_inclusive_boundaries_exact_total_and_fallback_id_link(self):
        first = self.expense(expense_date=date(2026, 9, 1), amount="10.25")
        last = self.expense(expense_date=date(2026, 9, 30), amount="12.50")
        outside = self.expense(expense_date=date(2026, 10, 1), amount="99.00")

        response = self.client.get(
            reverse("reports_expenses"),
            {"date_from": "2026-09-01", "date_to": "2026-09-30"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Expense #{first.pk}')
        self.assertContains(response, f'href="{reverse("expense_detail", args=[first.pk])}"')
        self.assertContains(response, f"Expense #{last.pk}")
        self.assertNotContains(response, f"Expense #{outside.pk}")
        self.assertContains(response, "NGN 22.75")
        self.assertContains(response, "Recorded")

    def test_default_recorded_report_excludes_voided_original_and_counts_recorded_replacement_once(self):
        original = self.expense(expense_date=date(2026, 9, 15), amount="10.00")
        replacement = correct_expense(
            business=self.business,
            actor=self.owner,
            expense=original,
            details={
                "date": date(2026, 9, 15),
                "category": Expense.Category.RENT,
                "description": "Corrected premises",
                "amount": Decimal("13.00"),
                "notes": "Corrected",
            },
        )

        recorded = self.client.get(reverse("reports_expenses"))
        voided = self.client.get(
            reverse("reports_expenses"), {"status": Expense.Status.VOIDED}
        )

        self.assertNotContains(recorded, f"Expense #{original.pk}")
        self.assertContains(recorded, f"Expense #{replacement.pk}")
        self.assertContains(recorded, "NGN 13.00")
        self.assertNotContains(recorded, "NGN 26.00")
        self.assertContains(voided, f"Expense #{original.pk}")
        self.assertNotContains(voided, f"Expense #{replacement.pk}")
        self.assertContains(
            voided,
            "Voided Expenses remain available for inspection. They are excluded from active totals.",
        )
        self.assertNotContains(voided, "Recorded Expense total")

    def test_explicit_voided_status_and_one_sided_date_filters_are_inclusive(self):
        older = self.expense(expense_date=date(2026, 8, 31), amount="5.00")
        older_voided = self.expense(expense_date=date(2026, 8, 31), amount="6.00")
        void_expense(business=self.business, actor=self.owner, expense=older_voided)
        voided = self.expense(expense_date=date(2026, 9, 30), amount="7.00")
        void_expense(business=self.business, actor=self.owner, expense=voided)
        newer = self.expense(expense_date=date(2026, 10, 1), amount="9.00")

        response = self.client.get(
            reverse("reports_expenses"),
            {"status": Expense.Status.VOIDED, "date_from": "2026-09-01"},
        )

        self.assertContains(response, f"Expense #{voided.pk}")
        self.assertNotContains(response, f"Expense #{older.pk}")
        self.assertNotContains(response, f"Expense #{older_voided.pk}")
        self.assertNotContains(response, f"Expense #{newer.pk}")
        self.assertContains(response, 'name="date_to" value=""')

        recorded_to = self.client.get(
            reverse("reports_expenses"),
            {"date_to": "2026-09-30"},
        )
        self.assertContains(recorded_to, f"Expense #{older.pk}")
        self.assertNotContains(recorded_to, f"Expense #{newer.pk}")
        self.assertContains(recorded_to, 'name="date_from" value=""')

    def test_reports_directory_discovers_expense_report(self):
        response = self.client.get(reverse("reports_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("reports_expenses")}">',
            html=False,
        )
        self.assertContains(response, "Expense report")

    def test_html_and_csv_keep_identical_scoped_results_and_filters(self):
        included = self.expense(expense_date=date(2026, 9, 15), amount="10.00")
        excluded = self.expense(expense_date=date(2026, 10, 1), amount="99.00")
        params = {"date_from": "2026-09-01", "date_to": "2026-09-30"}

        html = self.client.get(reverse("reports_expenses"), params)
        csv_response = self.client.get(reverse("reports_expenses_csv"), params)
        rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))

        self.assertContains(
            html,
            f'{reverse("reports_expenses_csv")}?status=recorded&date_from=2026-09-01&date_to=2026-09-30'.replace(
                "&", "&amp;"
            ),
        )
        self.assertContains(html, f"Expense #{included.pk}")
        self.assertNotContains(html, f"Expense #{excluded.pk}")
        self.assertEqual(rows[1][1], f"Expense #{included.pk}")
        self.assertEqual(len(rows), 2)

    def test_csv_has_stable_utf8_headings_iso_dates_two_decimals_and_safe_all_text_columns(self):
        expense = self.expense(
            expense_date=date(2026, 9, 15),
            amount="20.10",
            description="\t=SUM(A1:A2)",
        )

        response = self.client.get(reverse("reports_expenses_csv"))
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="expenses-report.csv"',
        )
        self.assertEqual(
            rows[0],
            ["Expense date", "Expense ID", "Category", "Description", "Status", "Amount"],
        )
        row = next(row for row in rows[1:] if row[1] == f"Expense #{expense.pk}")
        self.assertEqual(row[0], expense.date.isoformat())
        self.assertEqual(row[2], "Rent")
        self.assertEqual(row[3], "'\t=SUM(A1:A2)")
        self.assertEqual(row[4], "Recorded")
        self.assertEqual(row[5], "20.10")

    def test_csv_neutralizes_formula_prefixes_in_description(self):
        for prefix in ("=", "+", "-", "@", "\t=", "\r=", "\n="):
            self.expense(
                expense_date=date(2026, 9, 15),
                description=f"{prefix}unsafe description",
            )

        response = self.client.get(reverse("reports_expenses_csv"))
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        descriptions = {row[3] for row in rows[1:]}
        self.assertTrue(
            {f"'{prefix}unsafe description" for prefix in ("=", "+", "-", "@", "\t=", "\r=", "\n=")}.issubset(
                descriptions
            )
        )

    def test_report_access_allows_owner_staff_and_demo_reads_but_denies_inactive_and_anonymous(self):
        for user in (self.owner, self.staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("reports_expenses")).status_code, 200)
            self.assertEqual(self.client.get(reverse("reports_expenses_csv")).status_code, 200)

        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("reports_expenses")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reports_expenses_csv")).status_code, 200)

        membership = Membership.objects.get(user=self.staff)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(reverse("reports_expenses")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports_expenses_csv")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reports_expenses")).status_code, 302)

    def test_report_isolates_other_business_and_handles_empty_results(self):
        own = self.expense(expense_date=date(2026, 9, 15), amount="10.00")
        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        other = Expense.objects.create(
            business=other_business,
            actor=other_owner,
            date=date(2026, 9, 15),
            category=Expense.Category.RENT,
            description="Hidden rent",
            amount=Decimal("100.00"),
        )

        isolated = self.client.get(reverse("reports_expenses"))
        empty = self.client.get(
            reverse("reports_expenses"),
            {"date_from": "2026-10-01", "date_to": "2026-10-31"},
        )

        self.assertContains(isolated, f"Expense #{own.pk}")
        self.assertNotContains(isolated, f"Expense #{other.pk}")
        self.assertNotContains(isolated, "100.00")
        self.assertContains(empty, "No recorded Expenses match these filters.")

    def test_invalid_status_malformed_and_reversed_filters_are_clear_and_have_no_export_rows(self):
        self.expense(expense_date=date(2026, 9, 15))
        params = {
            "status": "draft",
            "date_from": "not-a-date",
            "date_to": "2026-09-31",
        }

        html = self.client.get(reverse("reports_expenses"), params)
        csv_response = self.client.get(reverse("reports_expenses_csv"), params)
        rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))

        self.assertContains(html, "Choose recorded or voided Expenses.")
        self.assertContains(html, "Enter a valid start date.")
        self.assertContains(html, "Enter a valid end date.")
        self.assertContains(html, 'name="date_from" value="not-a-date"')
        self.assertContains(html, 'name="date_to" value="2026-09-31"')
        self.assertNotContains(html, "Export CSV")
        self.assertNotContains(html, "Expense #")
        self.assertEqual(len(rows), 1)

        reversed_params = {"date_from": "2026-09-30", "date_to": "2026-09-01"}
        reversed_html = self.client.get(reverse("reports_expenses"), reversed_params)
        reversed_csv = self.client.get(reverse("reports_expenses_csv"), reversed_params)
        self.assertContains(reversed_html, "End date cannot be earlier than start date.")
        self.assertNotContains(reversed_html, "Export CSV")
        self.assertEqual(
            len(list(csv.reader(StringIO(reversed_csv.content.decode("utf-8"))))), 1
        )

    @override_settings(TIME_ZONE="Africa/Lagos")
    def test_omitted_dates_default_to_current_lagos_calendar_month_at_utc_boundary(self):
        utc_now = datetime(2026, 9, 30, 23, 30, tzinfo=datetime_timezone.utc)
        lagos_today = utc_now.astimezone(ZoneInfo("Africa/Lagos")).date()
        with patch("reports.expense.timezone.localdate", return_value=lagos_today):
            included = self.expense(expense_date=date(2026, 10, 1), amount="10.00")
            excluded = self.expense(expense_date=date(2026, 9, 30), amount="99.00")
            html = self.client.get(reverse("reports_expenses"))
            csv_response = self.client.get(reverse("reports_expenses_csv"))

        self.assertContains(html, 'name="date_from" value="2026-10-01"')
        self.assertContains(html, 'name="date_to" value="2026-10-31"')
        self.assertContains(html, f"Expense #{included.pk}")
        self.assertNotContains(html, f"Expense #{excluded.pk}")
        rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))
        self.assertEqual(rows[1][1], f"Expense #{included.pk}")
        self.assertEqual(len(rows), 2)
