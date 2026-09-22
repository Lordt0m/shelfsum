import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
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


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ResponsiveLayoutTests(TestCase):
    def test_viewport_meta_tag_present_on_rendered_pages(self):
        for route_name in ("landing", "sign_in", "register"):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(
                response,
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
            )

    def test_authenticated_navigation_rendered_in_responsive_header(self):
        user = get_user_model().objects.create_user(
            email="member@example.com", password="safe-password-123"
        )
        business = Business.objects.create(name="Responsive Test Shop")
        Membership.objects.create(
            user=user, business=business, role=Membership.Role.OWNER
        )
        self.client.force_login(user)

        response = self.client.get(reverse("business_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
        )
        self.assertContains(response, 'class="site-header"')
        self.assertContains(response, '<nav aria-label="Account navigation">')
        self.assertContains(response, reverse("audit_event_list"))
        self.assertContains(response, reverse("reports_index"))

    def test_stylesheet_enforces_responsive_contracts_and_clean_breakpoints(self):
        css_path = Path(settings.BASE_DIR) / "static" / "css" / "site.css"
        css = css_path.read_text(encoding="utf-8")

        # Base header wraps so brand and links do not cause horizontal overflow
        header_block = re.search(r"\.site-header\s*\{([^}]+)\}", css)
        self.assertIsNotNone(header_block, ".site-header block not found in site.css")
        self.assertIn("flex-wrap: wrap;", header_block.group(1))

        # Base navigation wraps on intermediate viewports
        nav_block = re.search(r"(?:^|\})\s*nav\s*\{([^}]+)\}", css)
        self.assertIsNotNone(nav_block, "nav block not found in site.css")
        self.assertIn("flex-wrap: wrap;", nav_block.group(1))

        # Media query covers tablet breakpoint at 768px (not the older 720px)
        media_match = re.search(r"@media\s*\(\s*max-width:\s*768px\s*\)\s*\{([\s\S]+?)\n\}", css)
        self.assertIsNotNone(media_match, "@media (max-width: 768px) block not found in site.css")
        media_css = media_match.group(1)

        # Nav in media query adjusts alignment/gap without redundant flex-wrap
        media_nav_block = re.search(r"nav\s*\{([^}]+)\}", media_css)
        self.assertIsNotNone(media_nav_block, "nav block inside @media not found")
        self.assertNotIn("flex-wrap", media_nav_block.group(1))
        self.assertIn("gap: 16px;", media_nav_block.group(1))

        # Report tables have horizontal scroll container to prevent page-level overflow
        table_wrap = re.search(r"\.report-table-wrap\s*\{([^}]+)\}", css)
        self.assertIsNotNone(table_wrap, ".report-table-wrap block not found in site.css")
        self.assertIn("overflow-x: auto;", table_wrap.group(1))
