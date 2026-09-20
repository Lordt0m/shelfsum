import contextlib
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, TestSuite

from core.demo_config import (
    DEMO_OWNER_EMAIL,
    DEMO_OWNER_PASSWORD,
    DEMO_STAFF_EMAIL,
    DEMO_STAFF_PASSWORD,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PROBE = """
import json
import django
from django.conf import settings

django.setup()
print(json.dumps({
    "debug": settings.DEBUG,
    "secret_key": settings.SECRET_KEY,
    "engine": settings.DATABASES["default"]["ENGINE"],
    "conn_max_age": settings.DATABASES["default"].get("CONN_MAX_AGE"),
    "conn_health_checks": settings.DATABASES["default"].get("CONN_HEALTH_CHECKS"),
    "sslmode": settings.DATABASES["default"].get("OPTIONS", {}).get("sslmode"),
    "allowed_hosts": settings.ALLOWED_HOSTS,
    "csrf_origins": settings.CSRF_TRUSTED_ORIGINS,
    "proxy_header": settings.SECURE_PROXY_SSL_HEADER,
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "session_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_secure": settings.CSRF_COOKIE_SECURE,
    "hsts": settings.SECURE_HSTS_SECONDS,
    "static_root": str(settings.STATIC_ROOT),
    "static_url": settings.STATIC_URL,
    "white_noise": "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE,
    "static_storage": settings.STORAGES["staticfiles"]["BACKEND"],
    "test_runner": getattr(settings, "TEST_RUNNER", ""),
    "silenced_checks": getattr(settings, "SILENCED_SYSTEM_CHECKS", []),
}))
"""


class ProductionSettingsSubprocessTests(TestCase):
    def run_probe(self, environment):
        env = os.environ.copy()
        for name in (
            "SHELFSUM_ENV",
            "CI",
            "SECRET_KEY",
            "DATABASE_URL",
            "RENDER_EXTERNAL_HOSTNAME",
            "RENDER",
            "ALLOWED_HOSTS",
            "CSRF_TRUSTED_ORIGINS",
            "STATIC_ROOT",
        ):
            env.pop(name, None)
        env.update(environment)
        env["DJANGO_SETTINGS_MODULE"] = "config.settings"
        return subprocess.run(
            [sys.executable, "-c", SETTINGS_PROBE],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_local_defaults_remain_runserver_compatible(self):
        result = self.run_probe(
            {
                "SHELFSUM_ENV": "development",
                "SECRET_KEY": "",
                "DATABASE_URL": "",
                "RENDER_EXTERNAL_HOSTNAME": "",
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"debug": true', result.stdout)
        self.assertIn('"secret_key": "django-insecure-local-development-only"', result.stdout)
        self.assertIn('"engine": "django.db.backends.sqlite3"', result.stdout)
        self.assertIn('"static_url": "/static/"', result.stdout)

    def test_postgresql_test_mode_requires_ci_and_database_url(self):
        valid = {
            "SHELFSUM_ENV": "postgresql-test",
            "CI": "true",
            "DATABASE_URL": "postgresql://user:password@example.com:5432/shelfsum",
        }
        result = self.run_probe(valid | {"CI": "false"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)

        result = self.run_probe(valid | {"CI": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)

        result = self.run_probe(valid | {"DATABASE_URL": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)

        result = self.run_probe(valid)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"engine": "django.db.backends.postgresql"', result.stdout)
        self.assertIn('"sslmode": null', result.stdout)
        self.assertIn('"allowed_hosts": []', result.stdout)
        self.assertIn('"csrf_origins": []', result.stdout)
        self.assertIn('"white_noise": false', result.stdout)
        self.assertIn('"test_runner": "config.test_runner.NoSkipTestRunner"', result.stdout)

    def test_postgresql_test_mode_rejects_unusable_or_non_postgresql_urls(self):
        for database_url in (
            "postgresql://",
            "postgresql://user:password@/shelfsum",
            "postgresql://user:password@example.com/",
            "postgresql://@example.com/shelfsum",
            "postgresql://user@example.com/shelfsum",
            "mysql://user:password@example.com/shelfsum",
        ):
            with self.subTest(database_url=database_url):
                result = self.run_probe(
                    {
                        "SHELFSUM_ENV": "postgresql-test",
                        "CI": "true",
                        "DATABASE_URL": database_url,
                    }
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ImproperlyConfigured", result.stderr)
                self.assertNotIn(database_url, result.stderr)

    def test_production_fails_closed_when_required_environment_is_missing(self):
        valid = {
            "SHELFSUM_ENV": "production",
            "SECRET_KEY": "production-test-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
            "DATABASE_URL": "postgresql://user:password@example.com:5432/shelfsum",
            "RENDER_EXTERNAL_HOSTNAME": "shelfsum.onrender.com",
        }
        for missing in ("SECRET_KEY", "DATABASE_URL", "RENDER_EXTERNAL_HOSTNAME"):
            with self.subTest(missing=missing):
                environment = valid.copy()
                environment[missing] = ""
                result = self.run_probe(environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ImproperlyConfigured", result.stderr)

        for weak_secret in (
            "django-insecure-local-development-only",
            "replace-with-a-random-production-secret",
            "django-insecure-production-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
            "short-production-secret",
            "0123456789abcdef0123456789abcdef",
            "a" * 64,
            "1234" * 11,
            "abcde" * 9,
            "A" * 40 + "BCDE",
            "abcde" * 10,
            "0123456789" * 5,
            "A" * 46 + "BCDE",
            "abcde" * 9 + "fghij",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            # Decodes to 32 bytes but fails decoded-byte diversity safeguard (< 5 distinct bytes):
            "YWJjZGFiZGNhY2JkYWRiY2JjYWRiZGFjY2RhYmRjY2E=",
            # Decodes to 32 bytes but fails decoded-byte frequency safeguard (> 10 occurrences of one byte):
            "YWVmYWhpYWtsYW5vYXFyYXR1YXd4YXp7YX1+YYCBYYM=",
        ):
            with self.subTest(weak_secret=weak_secret):
                environment = valid.copy()
                environment["SECRET_KEY"] = weak_secret
                result = self.run_probe(environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ImproperlyConfigured", result.stderr)

    def test_production_accepts_strong_render_generated_secret(self):
        render_secrets = (
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
            "-_-_MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmE=",
        )
        for secret in render_secrets:
            with self.subTest(secret=secret):
                result = self.run_probe(
                    {
                        "SHELFSUM_ENV": "production",
                        "SECRET_KEY": secret,
                        "DATABASE_URL": "postgresql://user:password@example.com:5432/shelfsum",
                        "RENDER_EXTERNAL_HOSTNAME": "shelfsum.onrender.com",
                    }
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('"debug": false', result.stdout)
                self.assertIn(f'"secret_key": "{secret}"', result.stdout)
                self.assertIn('"silenced_checks": ["security.W009"]', result.stdout)

    def test_blank_or_absent_environment_fails_when_production_signals_are_present(self):
        signals = {
            "DATABASE_URL": "postgresql://user:password@example.com:5432/shelfsum",
            "RENDER": "true",
            "RENDER_EXTERNAL_HOSTNAME": "shelfsum.onrender.com",
        }
        for signal, value in signals.items():
            for blank_environment in (True, False):
                with self.subTest(signal=signal, blank_environment=blank_environment):
                    environment = {signal: value}
                    if blank_environment:
                        environment["SHELFSUM_ENV"] = ""
                    result = self.run_probe(environment)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("ImproperlyConfigured", result.stderr)

    def test_production_rejects_structurally_unusable_database_urls(self):
        urls = (
            "postgresql://",
            "postgresql://user:pass@/shelfsum",
            "postgresql://user:pass@example.com/",
            "postgresql://@example.com/shelfsum",
            "postgresql://user@example.com/shelfsum",
            "mysql://user:pass@example.com/shelfsum",
        )
        for database_url in urls:
            with self.subTest(database_url=database_url):
                result = self.run_probe(
                    {
                        "SHELFSUM_ENV": "production",
                        "SECRET_KEY": "production-test-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
                        "DATABASE_URL": database_url,
                        "RENDER_EXTERNAL_HOSTNAME": "shelfsum.onrender.com",
                    }
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ImproperlyConfigured", result.stderr)
                self.assertNotIn(database_url, result.stderr)

    def test_production_uses_ssl_postgres_and_explicit_https_safety(self):
        result = self.run_probe(
            {
                "SHELFSUM_ENV": "production",
                "SECRET_KEY": "production-test-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
                "DATABASE_URL": "postgresql://user:password@example.com:5432/shelfsum",
                "RENDER_EXTERNAL_HOSTNAME": "shelfsum.onrender.com",
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"debug": false', result.stdout)
        self.assertIn('"static_url": "/static/"', result.stdout)
        self.assertIn('"engine": "django.db.backends.postgresql"', result.stdout)
        self.assertIn('"conn_max_age": 600', result.stdout)
        self.assertIn('"conn_health_checks": true', result.stdout)
        self.assertIn('"sslmode": "require"', result.stdout)
        self.assertIn('"allowed_hosts": ["shelfsum.onrender.com"]', result.stdout)
        self.assertIn('"csrf_origins": ["https://shelfsum.onrender.com"]', result.stdout)
        self.assertIn('"proxy_header": ["HTTP_X_FORWARDED_PROTO", "https"]', result.stdout)
        self.assertIn('"ssl_redirect": true', result.stdout)
        self.assertIn('"session_secure": true', result.stdout)
        self.assertIn('"csrf_secure": true', result.stdout)
        self.assertIn('"hsts": 31536000', result.stdout)
        self.assertIn('"white_noise": true', result.stdout)
        self.assertIn(
            '"static_storage": "whitenoise.storage.CompressedManifestStaticFilesStorage"',
            result.stdout,
        )
        self.assertIn('"silenced_checks": []', result.stdout)

    def test_explicit_csrf_origins_are_https_structural_and_business_scoped(self):
        valid = {
            "SHELFSUM_ENV": "production",
            "SECRET_KEY": "production-test-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
            "DATABASE_URL": "postgresql://user:password@example.com:5432/shelfsum",
            "ALLOWED_HOSTS": "example.com,.example.com",
        }
        accepted = valid | {"CSRF_TRUSTED_ORIGINS": "https://shop.example.com"}
        result = self.run_probe(accepted)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"csrf_origins": ["https://shop.example.com"]', result.stdout)

        for origin in (
            "http://example.com",
            "https://other.example.net",
            "https://user:password@example.com",
            "https://example.com/path",
            "https://example.com?next=/",
            "https://example.com#fragment",
            "https://example..com",
        ):
            with self.subTest(origin=origin):
                result = self.run_probe(valid | {"CSRF_TRUSTED_ORIGINS": origin})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ImproperlyConfigured", result.stderr)

    def test_production_collectstatic_succeeds_in_a_temporary_output(self):
        with tempfile.TemporaryDirectory() as static_root:
            env = {
                "SHELFSUM_ENV": "production",
                "SECRET_KEY": "production-test-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
                "DATABASE_URL": "postgresql://user:password@example.com:5432/shelfsum",
                "RENDER_EXTERNAL_HOSTNAME": "shelfsum.onrender.com",
                "STATIC_ROOT": static_root,
            }
            environment = os.environ.copy()
            for name in (
                "SHELFSUM_ENV",
                "SECRET_KEY",
                "DATABASE_URL",
                "RENDER_EXTERNAL_HOSTNAME",
                "ALLOWED_HOSTS",
                "CSRF_TRUSTED_ORIGINS",
                "STATIC_ROOT",
            ):
                environment.pop(name, None)
            environment.update(env)
            environment["DJANGO_SETTINGS_MODULE"] = "config.settings"
            result = subprocess.run(
                [sys.executable, "manage.py", "collectstatic", "--no-input"],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("static files copied", result.stdout)
            self.assertIn(static_root, result.stdout)
            self.assertTrue((Path(static_root) / "staticfiles.json").exists())


class ReleaseMetadataTests(TestCase):
    def test_provider_metadata_and_release_script_are_pinned_and_safe(self):
        requirements = (PROJECT_ROOT / "requirements.txt").read_text()
        self.assertIn("Django==5.2.17", requirements)
        self.assertIn("dj-database-url==3.1.2", requirements)
        self.assertIn("psycopg[binary]==3.3.5", requirements)
        self.assertIn("gunicorn==26.2.0", requirements)
        self.assertIn("whitenoise==6.12.0", requirements)

        build_script = (PROJECT_ROOT / "build.sh").read_text()
        self.assertIn("python -m pip install -r requirements.txt", build_script)
        self.assertIn("python manage.py collectstatic --no-input", build_script)
        self.assertIn("python manage.py migrate", build_script)
        self.assertIn("python manage.py seed_demo", build_script)

        render = (PROJECT_ROOT / "render.yaml").read_text()
        for expected in (
            "runtime: python",
            "region: frankfurt",
            "plan: free",
            "healthCheckPath: /health/",
            "value: production",
            "generateValue: true",
            "sync: false",
            "startCommand: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT",
        ):
            self.assertIn(expected, render)

        command = (PROJECT_ROOT / "core" / "management" / "commands" / "seed_demo.py").read_text()
        for credential in (
            DEMO_OWNER_EMAIL,
            DEMO_OWNER_PASSWORD,
            DEMO_STAFF_EMAIL,
            DEMO_STAFF_PASSWORD,
        ):
            self.assertNotIn(credential, command)


class PostgreSQLTestRunnerContractTests(TestCase):
    def test_no_skip_runner_turns_skips_into_failures(self):
        from config.test_runner import NoSkipTestRunner

        class SkippedTest(TestCase):
            def test_database_dependent_check(self):
                self.skipTest("requires PostgreSQL")

        suite = TestSuite([SkippedTest("test_database_dependent_check")])
        with contextlib.redirect_stderr(io.StringIO()):
            result = NoSkipTestRunner(verbosity=0).run_suite(suite)

        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.skipped, [])
        self.assertIn("requires PostgreSQL", result.failures[0][1])


class ContinuousIntegrationWorkflowContractTests(TestCase):
    def test_postgresql_release_workflow_is_pinned_and_runs_all_gates(self):
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        for expected in (
            "runs-on: ubuntu-latest",
            "permissions:\n  contents: read",
            "actions/checkout@v7",
            "actions/setup-python@v7",
            'python-version: "3.13.14"',
            "cache: pip",
            "image: postgres:17",
            "CI: true",
            "SHELFSUM_ENV: postgresql-test",
            "DATABASE_URL: postgresql://shelfsum:shelfsum@localhost:5432/shelfsum",
            "python -m pip install -r requirements.txt",
            "python manage.py shell -c",
            "connection.vendor == 'postgresql'",
            "python manage.py check",
            "python manage.py makemigrations --check --dry-run",
            "python manage.py migrate --no-input",
            "python manage.py seed_demo\n          python manage.py seed_demo",
            "python manage.py test",
            "SHELFSUM_ENV: production",
            "python manage.py collectstatic --no-input",
            "python manage.py check --deploy",
        ):
            self.assertIn(expected, workflow)
