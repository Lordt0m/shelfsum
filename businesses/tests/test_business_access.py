from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from businesses.models import Business, Membership


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

    def test_existing_member_cannot_create_a_second_business_with_crafted_post(self):
        business = Business.objects.create(name="First Shop")
        Membership.objects.create(
            user=self.user, business=business, role=Membership.Role.OWNER
        )

        response = self.client.post(reverse("business_create"), {"name": "Second Shop"})

        self.assertRedirects(response, reverse("business_home"))
        self.assertEqual(Business.objects.count(), 1)


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
