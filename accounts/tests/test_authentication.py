from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class RegistrationTests(TestCase):
    def test_visitor_can_register_with_email_and_is_guided_to_business_creation(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "Owner@Example.com",
                "password1": "correct horse battery staple",
                "password2": "correct horse battery staple",
            },
        )

        user = get_user_model().objects.get()
        self.assertEqual(user.email, "owner@example.com")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("business_create"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_email_is_rejected_without_discarding_the_form(self):
        get_user_model().objects.create_user(
            email="owner@example.com", password="existing-password"
        )

        response = self.client.post(
            reverse("register"),
            {
                "email": "OWNER@example.com",
                "password1": "correct horse battery staple",
                "password2": "correct horse battery staple",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already registered")
        self.assertEqual(get_user_model().objects.count(), 1)


class SessionAuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="owner@example.com", password="original-password-123"
        )

    def test_user_can_sign_in_with_email_and_sign_out_with_post(self):
        response = self.client.post(
            reverse("sign_in"),
            {"username": self.user.email, "password": "original-password-123"},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(reverse("sign_out"))
        self.assertRedirects(response, reverse("landing"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_email_sign_in_is_case_insensitive(self):
        response = self.client.post(
            reverse("sign_in"),
            {"username": "OWNER@EXAMPLE.COM", "password": "original-password-123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_authenticated_user_can_change_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "original-password-123",
                "new_password1": "replacement-password-456",
                "new_password2": "replacement-password-456",
            },
        )

        self.assertRedirects(response, reverse("password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("replacement-password-456"))
