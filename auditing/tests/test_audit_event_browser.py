from datetime import datetime, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from auditing.models import AuditEvent
from businesses.models import Business, Membership


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuditEventBrowserRequestTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="owner@example.com", password="password"
        )
        self.deactivated_actor = user_model.objects.create_user(
            email="former-staff@example.com", password="password"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        self.former_membership = Membership.objects.create(
            user=self.deactivated_actor,
            business=self.business,
            role=Membership.Role.STAFF,
        )
        self.client.force_login(self.owner)

    def event(self, *, business, actor, action, summary, at):
        event = AuditEvent.objects.create(
            business=business,
            actor=actor,
            action=action,
            object_type="catalogue.Product",
            object_identifier="1",
            summary=summary,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f'UPDATE "{AuditEvent._meta.db_table}" SET "created_at" = %s WHERE "id" = %s',
                [at, event.pk],
            )
        return event

    def test_current_business_list_includes_deactivated_actor_and_excludes_in_range_foreign_event(self):
        own_event = self.event(
            business=self.business,
            actor=self.deactivated_actor,
            action="product.updated",
            summary="Former staff updated Beans.",
            at=datetime(2026, 9, 15, 10, tzinfo=datetime_timezone.utc),
        )
        Membership.objects.filter(pk=self.former_membership.pk).update(is_active=False)
        other_business = Business.objects.create(name="Other Shop")
        foreign_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        Membership.objects.create(
            user=foreign_owner,
            business=other_business,
            role=Membership.Role.OWNER,
        )
        foreign_event = self.event(
            business=other_business,
            actor=foreign_owner,
            action="product.updated",
            summary="Foreign event must stay hidden.",
            at=datetime(2026, 9, 15, 11, tzinfo=datetime_timezone.utc),
        )

        response = self.client.get(
            reverse("audit_event_list"),
            {"date_from": "2026-09-01", "date_to": "2026-09-30"},
        )

        shown_ids = [row.event.pk for row in response.context["browser"].rows]
        self.assertEqual(shown_ids, [own_event.pk])
        self.assertNotIn(foreign_event.pk, shown_ids)
        self.assertContains(response, self.deactivated_actor.email)
        self.assertNotContains(response, "Foreign event must stay hidden.")

    def test_newest_first_actor_and_action_filters_keep_current_business_choices_only(self):
        staff_event = self.event(
            business=self.business,
            actor=self.deactivated_actor,
            action="product.updated",
            summary="Former staff event.",
            at=datetime(2026, 9, 15, 10, tzinfo=datetime_timezone.utc),
        )
        owner_event = self.event(
            business=self.business,
            actor=self.owner,
            action="product.created",
            summary="Owner event.",
            at=datetime(2026, 9, 15, 11, tzinfo=datetime_timezone.utc),
        )
        foreign_business = Business.objects.create(name="Foreign Shop")
        foreign_actor = get_user_model().objects.create_user(
            email="foreign@example.com", password="password"
        )
        Membership.objects.create(user=foreign_actor, business=foreign_business, role=Membership.Role.OWNER)
        self.event(
            business=foreign_business,
            actor=foreign_actor,
            action="foreign.action",
            summary="Foreign-only event.",
            at=datetime(2026, 9, 15, 12, tzinfo=datetime_timezone.utc),
        )

        all_events = self.client.get(reverse("audit_event_list"))
        actor_filtered = self.client.get(reverse("audit_event_list"), {"actor": self.deactivated_actor.pk})
        action_filtered = self.client.get(reverse("audit_event_list"), {"action": "product.created"})

        self.assertEqual([row.event.pk for row in all_events.context["browser"].rows], [owner_event.pk, staff_event.pk])
        self.assertEqual([row.event.pk for row in actor_filtered.context["browser"].rows], [staff_event.pk])
        self.assertEqual([row.event.pk for row in action_filtered.context["browser"].rows], [owner_event.pk])
        self.assertContains(all_events, f'<option value="{self.deactivated_actor.pk}">{self.deactivated_actor.email}</option>')
        self.assertNotContains(all_events, foreign_actor.email)
        self.assertContains(all_events, '<option value="product.created">product.created</option>')
        self.assertNotContains(all_events, "foreign.action")

    def test_lagos_date_boundaries_are_inclusive_and_one_sided(self):
        before = self.event(
            business=self.business, actor=self.owner, action="before", summary="Before.",
            at=datetime(2026, 8, 31, 22, 59, 59, tzinfo=datetime_timezone.utc),
        )
        start = self.event(
            business=self.business, actor=self.owner, action="start", summary="Start.",
            at=datetime(2026, 8, 31, 23, tzinfo=datetime_timezone.utc),
        )
        end = self.event(
            business=self.business, actor=self.owner, action="end", summary="End.",
            at=datetime(2026, 9, 30, 22, 59, 59, tzinfo=datetime_timezone.utc),
        )
        after = self.event(
            business=self.business, actor=self.owner, action="after", summary="After.",
            at=datetime(2026, 9, 30, 23, tzinfo=datetime_timezone.utc),
        )

        inclusive = self.client.get(reverse("audit_event_list"), {"date_from": "2026-09-01", "date_to": "2026-09-30"})
        from_only = self.client.get(reverse("audit_event_list"), {"date_from": "2026-09-01"})
        to_only = self.client.get(reverse("audit_event_list"), {"date_to": "2026-09-30"})

        self.assertEqual({row.event.pk for row in inclusive.context["browser"].rows}, {start.pk, end.pk})
        self.assertEqual({row.event.pk for row in from_only.context["browser"].rows}, {start.pk, end.pk, after.pk})
        self.assertEqual({row.event.pk for row in to_only.context["browser"].rows}, {before.pk, start.pk, end.pk})
        self.assertContains(inclusive, "2026-09-01 00:00:00 +0100")
        self.assertContains(inclusive, "2026-09-30 23:59:59 +0100")

    @override_settings(TIME_ZONE="UTC")
    def test_timestamp_display_remains_explicitly_lagos_stable(self):
        self.event(
            business=self.business, actor=self.owner, action="product.created", summary="A real event.",
            at=datetime(2026, 9, 15, 10, tzinfo=datetime_timezone.utc),
        )

        response = self.client.get(reverse("audit_event_list"), {"date_from": "2026-09-15", "date_to": "2026-09-15"})

        self.assertContains(response, "2026-09-15 11:00:00 +0100")
        self.assertNotContains(response, "2026-09-15 10:00:00 +0000")

    def test_invalid_values_preserve_raw_input_and_do_not_show_events(self):
        self.event(
            business=self.business, actor=self.owner, action="product.created", summary="A real event.",
            at=datetime(2026, 9, 15, 10, tzinfo=datetime_timezone.utc),
        )

        response = self.client.get(reverse("audit_event_list"), {
            "actor": "999999", "action": "not.real", "date_from": "not-a-date", "date_to": "2026-09-31",
        })
        reversed_response = self.client.get(reverse("audit_event_list"), {"date_from": "2026-09-30", "date_to": "2026-09-01"})

        self.assertContains(response, "Choose an actor from this Business.")
        self.assertContains(response, "Choose an action from this Business.")
        self.assertContains(response, "Enter a valid start date.")
        self.assertContains(response, "Enter a valid end date.")
        self.assertContains(response, '<option value="999999" selected>999999</option>')
        self.assertContains(response, '<option value="not.real" selected>not.real</option>')
        self.assertContains(response, 'name="date_from" value="not-a-date"')
        self.assertContains(response, 'name="date_to" value="2026-09-31"')
        self.assertNotContains(response, "A real event.")
        self.assertContains(reversed_response, "End date cannot be earlier than start date.")

    def test_empty_access_and_discovery_are_safe_for_all_read_roles(self):
        self.event(
            business=self.business, actor=self.owner, action="product.created", summary="A real event.",
            at=datetime(2026, 9, 15, 10, tzinfo=datetime_timezone.utc),
        )
        staff = get_user_model().objects.create_user(email="staff@example.com", password="password")
        staff_membership = Membership.objects.create(user=staff, business=self.business, role=Membership.Role.STAFF)
        for user in (self.owner, staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("audit_event_list")).status_code, 200)
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.assertEqual(self.client.get(reverse("audit_event_list")).status_code, 200)
        Membership.objects.filter(pk=staff_membership.pk).update(is_active=False)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("audit_event_list")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("audit_event_list")).status_code, 302)
        self.client.force_login(self.owner)
        empty = self.client.get(reverse("audit_event_list"), {"action": "product.created", "date_from": "2030-01-01"})
        dashboard = self.client.get(reverse("business_home"))
        browser = self.client.get(reverse("audit_event_list"))
        self.assertContains(empty, "No Audit Events match these filters.")
        self.assertContains(dashboard, f'href="{reverse("audit_event_list")}"')
        self.assertContains(browser, "<caption>Audit Events matching the selected filters</caption>")
        for heading in ("Lagos timestamp", "Actor", "Action", "Summary"):
            self.assertContains(browser, f'<th scope="col">{heading}</th>')
