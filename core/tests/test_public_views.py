from django.test import TestCase
from django.urls import reverse

from core.demo import (
    DEMO_OWNER_EMAIL,
    DEMO_OWNER_PASSWORD,
    DEMO_STAFF_EMAIL,
    DEMO_STAFF_PASSWORD,
)


class LandingPageTests(TestCase):
    def test_visitor_can_understand_the_product(self):
        response = self.client.get(reverse("landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Know what is on your shelves")
        self.assertContains(response, "Built for small shops")
        self.assertContains(response, DEMO_OWNER_EMAIL)
        self.assertContains(response, DEMO_OWNER_PASSWORD)
        self.assertContains(response, DEMO_STAFF_EMAIL)
        self.assertContains(response, DEMO_STAFF_PASSWORD)
        self.assertContains(response, "fictional")
        self.assertContains(response, "read-only")
        self.assertNotContains(response, "Demo access is coming")


class HealthCheckTests(TestCase):
    def test_monitor_can_confirm_the_application_is_ready(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
