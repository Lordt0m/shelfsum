from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from threading import Barrier, Thread
from unittest import skipUnless
from unittest.mock import patch

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from businesses.services import (
    BusinessCreationError,
    MembershipAssignmentError,
    add_staff_member,
    create_business_for_owner,
    deactivate_staff_member,
    update_business_settings,
)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BusinessCreationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="owner@example.com", password="safe-password-123"
        )
        self.client.force_login(self.user)

    def test_user_without_membership_is_guided_to_business_creation(self):
        response = self.client.get(reverse("business_home"))

        self.assertRedirects(response, reverse("business_create"))

    def test_user_can_create_one_business_and_becomes_its_owner(self):
        response = self.client.post(
            reverse("business_create"),
            {"name": "Balogun Corner Shop", "phone_number": "08012345678", "address": "Lagos"},
        )

        membership = Membership.objects.select_related("business").get(user=self.user)
        self.assertRedirects(response, reverse("business_home"))
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.business.name, "Balogun Corner Shop")
        event = AuditEvent.objects.get(business=membership.business)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.action, "business.created")
        self.assertEqual(event.object_identifier, str(membership.business.pk))

    def test_existing_member_cannot_create_a_second_business_with_crafted_post(self):
        business = Business.objects.create(name="First Shop")
        Membership.objects.create(
            user=self.user, business=business, role=Membership.Role.OWNER
        )

        response = self.client.post(reverse("business_create"), {"name": "Second Shop"})

        self.assertRedirects(response, reverse("business_home"))
        self.assertEqual(Business.objects.count(), 1)

    def test_creation_service_rejects_any_existing_membership_with_stable_error(self):
        business = Business.objects.create(name="First Shop")
        Membership.objects.create(
            user=self.user, business=business, role=Membership.Role.OWNER
        )

        with self.assertRaisesRegex(
            BusinessCreationError, r"Your account already belongs to a Business\."
        ):
            create_business_for_owner(
                actor=self.user,
                name="Second Shop",
                phone_number="08000000000",
                address="Lagos",
            )

        self.assertEqual(Business.objects.count(), 1)

    def test_creation_service_rolls_back_business_and_membership_when_audit_fails(self):
        with patch(
            "businesses.services.record_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
                create_business_for_owner(
                    actor=self.user,
                    name="Balogun Corner Shop",
                    phone_number="08012345678",
                    address="Lagos",
                )

        self.assertFalse(Business.objects.exists())
        self.assertFalse(Membership.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_create_request_propagates_audit_integrity_error_after_rollback(self):
        with patch(
            "businesses.services.record_audit_event",
            side_effect=IntegrityError("audit unavailable"),
        ):
            with self.assertRaisesRegex(IntegrityError, "audit unavailable"):
                self.client.post(
                    reverse("business_create"),
                    {
                        "name": "Balogun Corner Shop",
                        "phone_number": "08012345678",
                        "address": "Lagos",
                    },
                )

        self.assertFalse(Business.objects.exists())
        self.assertFalse(Membership.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_inactive_member_gets_stable_denial_instead_of_redirect_loop(self):
        business = Business.objects.create(name="Former Shop")
        Membership.objects.create(
            user=self.user,
            business=business,
            role=Membership.Role.STAFF,
            is_active=False,
        )

        home_response = self.client.get(reverse("business_home"))
        create_response = self.client.get(reverse("business_create"))

        self.assertEqual(home_response.status_code, 403)
        self.assertContains(home_response, "access is inactive", status_code=403)
        self.assertEqual(create_response.status_code, 403)
        self.assertContains(create_response, "access is inactive", status_code=403)


@skipUnless(
    connection.vendor == "postgresql",
    "Release verification only: requires PostgreSQL row locks and independent database connections.",
)
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BusinessCreationPostgreSQLConcurrencyTests(TransactionTestCase):
    """Exercise the same-actor Business creation race against PostgreSQL row locks."""

    reset_sequences = True

    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            email="owner@example.com", password="safe-password-123"
        )

    def test_same_actor_race_creates_one_business_and_stable_duplicate_error(self):
        start = Barrier(2)
        errors = []

        def worker(name):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                start.wait(timeout=10)
                create_business_for_owner(
                    actor=actor,
                    name=name,
                    phone_number="08012345678",
                    address="Lagos",
                )
            except Exception as error:
                errors.append(error)
            finally:
                close_old_connections()

        first = Thread(target=worker, args=("First Shop",), name="business-create-1")
        second = Thread(target=worker, args=("Second Shop",), name="business-create-2")
        first.start()
        second.start()
        first.join(timeout=15)
        second.join(timeout=15)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], BusinessCreationError)
        self.assertEqual(
            str(errors[0]), "Your account already belongs to a Business."
        )
        self.assertEqual(Business.objects.count(), 1)
        self.assertEqual(
            Membership.objects.filter(
                user=self.actor, role=Membership.Role.OWNER, is_active=True
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                actor=self.actor, action="business.created"
            ).count(),
            1,
        )

@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BusinessAccessTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="safe-password-123"
        )
        self.staff = get_user_model().objects.create_user(
            email="staff@example.com", password="safe-password-123"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )

    def test_protected_business_home_redirects_visitor_to_sign_in(self):
        response = self.client.get(reverse("business_home"))

        self.assertRedirects(
            response,
            f'{reverse("sign_in")}?next={reverse("business_home")}',
        )

    def test_owner_can_view_and_update_business_settings(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("business_settings"),
            {"name": "Updated Shop", "phone_number": "", "address": "Ikeja"},
        )

        self.assertRedirects(response, reverse("business_settings"))
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Updated Shop")
        self.assertEqual(self.business.address, "Ikeja")
        event = AuditEvent.objects.get(business=self.business)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.action, "business.updated")
        self.assertNotIn("080", event.summary)
        self.assertNotIn("Ikeja", event.summary)

    def test_settings_form_errors_remain_on_the_form_without_writing(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("business_settings"),
            {"name": "", "phone_number": "08012345678", "address": "Ikeja"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Balogun Corner Shop")
        self.assertFalse(AuditEvent.objects.filter(business=self.business).exists())

    def test_staff_member_cannot_view_or_update_business_settings(self):
        self.client.force_login(self.staff)

        get_response = self.client.get(reverse("business_settings"))
        post_response = self.client.post(
            reverse("business_settings"), {"name": "Hijacked Shop"}
        )

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Balogun Corner Shop")

    def test_demo_business_settings_reject_owner_writes(self):
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("business_settings"), {"name": "Changed Demo"}
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "read-only", status_code=403)
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Balogun Corner Shop")

    def test_settings_service_rejects_demo_staff_inactive_and_foreign_actors(self):
        other_owner = get_user_model().objects.create_user(
            email="other-owner@example.com", password="safe-password-123"
        )
        Membership.objects.create(
            user=other_owner,
            business=Business.objects.create(name="Other Shop"),
            role=Membership.Role.OWNER,
        )
        inactive_owner = get_user_model().objects.create_user(
            email="inactive-owner@example.com", password="safe-password-123"
        )
        Membership.objects.create(
            user=inactive_owner,
            business=self.business,
            role=Membership.Role.STAFF,
            is_active=False,
        )

        cases = (
            self.staff,
            other_owner,
            inactive_owner,
        )
        for actor in cases:
            with self.subTest(actor=actor.email), self.assertRaises(PermissionDenied):
                update_business_settings(
                    business=self.business,
                    actor=actor,
                    name="Changed Shop",
                    phone_number="08000000000",
                    address="Ikeja",
                )

        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        with self.assertRaises(PermissionDenied):
            update_business_settings(
                business=self.business,
                actor=self.owner,
                name="Changed Demo",
                phone_number="",
                address="",
            )
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Balogun Corner Shop")

    def test_settings_service_noop_does_not_emit_an_audit_event(self):
        updated = update_business_settings(
            business=self.business,
            actor=self.owner,
            name=self.business.name,
            phone_number=self.business.phone_number,
            address=self.business.address,
        )

        self.assertEqual(updated.pk, self.business.pk)
        self.assertFalse(AuditEvent.objects.filter(business=self.business).exists())

    def test_settings_service_rolls_back_changes_when_audit_fails(self):
        with patch(
            "businesses.services.record_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
                update_business_settings(
                    business=self.business,
                    actor=self.owner,
                    name="Should Roll Back",
                    phone_number="08000000000",
                    address="Ikeja",
                )

        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Balogun Corner Shop")
        self.assertEqual(self.business.phone_number, "")
        self.assertEqual(self.business.address, "")
        self.assertFalse(AuditEvent.objects.filter(business=self.business).exists())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class StaffMembershipTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="safe-password-123"
        )
        self.staff = get_user_model().objects.create_user(
            email="staff@example.com", password="safe-password-123"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        self.client.force_login(self.owner)

    def test_owner_can_add_an_unassigned_registered_staff_member(self):
        response = self.client.post(reverse("staff_member_add"), {"email": self.staff.email})

        membership = Membership.objects.get(user=self.staff)
        self.assertRedirects(response, reverse("staff_member_list"))
        self.assertEqual(membership.business, self.business)
        self.assertEqual(membership.role, Membership.Role.STAFF)
        self.assertTrue(membership.is_active)
        self.assertTrue(
            AuditEvent.objects.filter(
                business=self.business,
                actor=self.owner,
                action="membership.staff_added",
                object_identifier=str(membership.pk),
            ).exists()
        )

    def test_add_staff_member_rejects_unknown_owner_duplicate_and_assigned_users(self):
        other_owner = get_user_model().objects.create_user(
            email="other-owner@example.com", password="safe-password-123"
        )
        other_business = Business.objects.create(name="Other Shop")
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )

        cases = (
            ("missing@example.com", "No registered user has that email address."),
            (self.owner.email, "You cannot add yourself as a Staff Member."),
            (self.staff.email, "That user already belongs to this Business."),
            (other_owner.email, "That user is already assigned to another Business."),
        )
        for email, error in cases:
            with self.subTest(email=email):
                response = self.client.post(reverse("staff_member_add"), {"email": email})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, error)

    def test_owner_can_list_and_deactivate_staff_without_losing_audit_attribution(self):
        membership = Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )
        AuditEvent.objects.create(
            business=self.business,
            actor=self.staff,
            action="product_created",
            object_type="catalogue.Product",
            object_identifier="1",
            summary="Created a Product.",
        )

        list_response = self.client.get(reverse("staff_member_list"))
        response = self.client.post(reverse("staff_member_deactivate", args=[membership.pk]))

        self.assertContains(list_response, self.staff.email)
        self.assertRedirects(response, reverse("staff_member_list"))
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)
        self.assertTrue(AuditEvent.objects.filter(actor=self.staff).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action="membership.staff_deactivated", object_identifier=str(membership.pk)
            ).exists()
        )

    def test_deactivated_staff_member_loses_business_access_immediately(self):
        membership = Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )
        self.client.post(reverse("staff_member_deactivate", args=[membership.pk]))

        self.client.force_login(self.staff)
        for url in (reverse("business_home"), reverse("product_list")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
                self.assertContains(response, "access is inactive", status_code=403)

    def test_staff_cannot_manage_business_settings_or_memberships(self):
        another_staff = get_user_model().objects.create_user(
            email="another-staff@example.com", password="safe-password-123"
        )
        Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )
        another_membership = Membership.objects.create(
            user=another_staff, business=self.business, role=Membership.Role.STAFF
        )
        self.client.force_login(self.staff)

        home_response = self.client.get(reverse("business_home"))
        for url in (reverse("business_settings"), reverse("staff_member_list")):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        add_response = self.client.post(reverse("staff_member_add"), {"email": self.owner.email})
        deactivate_response = self.client.post(
            reverse("staff_member_deactivate", args=[another_membership.pk])
        )
        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(deactivate_response.status_code, 403)
        self.assertNotContains(home_response, "Business settings")
        self.assertNotContains(home_response, "Staff Members")
        self.assertTrue(another_membership.is_active)
        self.assertEqual(Membership.objects.filter(business=self.business).count(), 3)

    def test_demo_business_rejects_membership_writes_at_request_boundary(self):
        existing_membership = Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )
        unassigned_user = get_user_model().objects.create_user(
            email="unassigned@example.com", password="safe-password-123"
        )
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])

        add_response = self.client.post(
            reverse("staff_member_add"), {"email": unassigned_user.email}
        )
        deactivate_response = self.client.post(
            reverse("staff_member_deactivate", args=[existing_membership.pk])
        )

        self.assertEqual(add_response.status_code, 403)
        self.assertContains(add_response, "read-only", status_code=403)
        self.assertEqual(deactivate_response.status_code, 403)
        existing_membership.refresh_from_db()
        self.assertTrue(existing_membership.is_active)
        self.assertFalse(Membership.objects.filter(user=unassigned_user).exists())

    def test_membership_identifiers_are_scoped_to_the_owners_business(self):
        other_owner = get_user_model().objects.create_user(
            email="other-owner@example.com", password="safe-password-123"
        )
        other_staff = get_user_model().objects.create_user(
            email="other-staff@example.com", password="safe-password-123"
        )
        other_business = Business.objects.create(name="Other Shop")
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        hidden_membership = Membership.objects.create(
            user=other_staff, business=other_business, role=Membership.Role.STAFF
        )

        response = self.client.post(
            reverse("staff_member_deactivate", args=[hidden_membership.pk])
        )

        self.assertEqual(response.status_code, 404)
        hidden_membership.refresh_from_db()
        self.assertTrue(hidden_membership.is_active)

    def test_services_enforce_owner_demo_and_business_boundaries(self):
        owner_membership = Membership.objects.get(user=self.owner)
        staff_membership = Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )
        unassigned_user = get_user_model().objects.create_user(
            email="unassigned@example.com", password="safe-password-123"
        )
        other_business = Business.objects.create(name="Other Shop")

        with self.assertRaises(PermissionDenied):
            add_staff_member(business=self.business, actor=self.staff, email="missing@example.com")
        with self.assertRaises(PermissionDenied):
            deactivate_staff_member(
                business=other_business, actor=self.owner, membership=staff_membership
            )
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        with self.assertRaises(PermissionDenied):
            add_staff_member(
                business=self.business, actor=self.owner, email=unassigned_user.email
            )
        with self.assertRaises(PermissionDenied):
            deactivate_staff_member(
                business=self.business, actor=self.owner, membership=staff_membership
            )
        self.assertTrue(owner_membership.is_active)
        self.assertFalse(Membership.objects.filter(user=unassigned_user).exists())
        self.assertFalse(AuditEvent.objects.filter(business=self.business).exists())

    def test_add_staff_member_rolls_back_when_auditing_fails(self):
        with patch(
            "businesses.services.record_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                add_staff_member(
                    business=self.business, actor=self.owner, email=self.staff.email
                )

        self.assertFalse(Membership.objects.filter(user=self.staff).exists())
        self.assertFalse(AuditEvent.objects.filter(business=self.business).exists())

    def test_deactivate_staff_member_rolls_back_when_auditing_fails(self):
        membership = Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )

        with patch(
            "businesses.services.record_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                deactivate_staff_member(
                    business=self.business, actor=self.owner, membership=membership
                )

        membership.refresh_from_db()
        self.assertTrue(membership.is_active)
        self.assertFalse(AuditEvent.objects.filter(business=self.business).exists())
