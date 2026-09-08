from django.test import TestCase
from django.urls import reverse


class LandingPageTests(TestCase):
    def test_visitor_can_understand_the_product(self):
        response = self.client.get(reverse("landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Know what is on your shelves")
        self.assertContains(response, "Built for small shops")
        self.assertContains(response, "Demo access is coming")


class HealthCheckTests(TestCase):
    def test_monitor_can_confirm_the_application_is_ready(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
