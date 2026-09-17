import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import TestCase


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
}))
"""


class ProductionSettingsSubprocessTests(TestCase):
    def run_probe(self, environment):
        env = os.environ.copy()
        for name in (
            "SHELFSUM_ENV",
            "SECRET_KEY",
            "DATABASE_URL",
            "RENDER_EXTERNAL_HOSTNAME",
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

    def test_production_fails_closed_when_required_environment_is_missing(self):
        valid = {
            "SHELFSUM_ENV": "production",
            "SECRET_KEY": "test-only-production-secret",
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

        local_secret = valid.copy()
        local_secret["SECRET_KEY"] = "django-insecure-local-development-only"
        result = self.run_probe(local_secret)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)

    def test_production_uses_ssl_postgres_and_explicit_https_safety(self):
        result = self.run_probe(
            {
                "SHELFSUM_ENV": "production",
                "SECRET_KEY": "test-only-production-secret",
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

    def test_production_collectstatic_succeeds_in_a_temporary_output(self):
        with tempfile.TemporaryDirectory() as static_root:
            env = {
                "SHELFSUM_ENV": "production",
                "SECRET_KEY": "test-only-production-secret",
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
            "gunicorn config.wsgi:application",
        ):
            self.assertIn(expected, render)
