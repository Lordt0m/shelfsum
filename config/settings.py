import base64
import binascii
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

LOCAL_SECRET_KEY = "django-insecure-local-development-only"
SECRET_KEY = LOCAL_SECRET_KEY
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "auditing",
    "businesses",
    "catalogue",
    "core",
    "inventory",
    "purchases",
    "sales",
    "expenses",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT") or BASE_DIR / "staticfiles")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "sign_in"
LOGIN_REDIRECT_URL = "business_home"


def _csv_environment_value(name):
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


def _production_hosts():
    hosts = _csv_environment_value("ALLOWED_HOSTS")
    if not hosts:
        hosts = _csv_environment_value("RENDER_EXTERNAL_HOSTNAME")
    unusable_host = any(
        host == "*"
        or "://" in host
        or "/" in host
        or any(character.isspace() for character in host)
        for host in hosts
    )
    if not hosts or unusable_host:
        raise ImproperlyConfigured(
            "Production requires a usable ALLOWED_HOSTS or RENDER_EXTERNAL_HOSTNAME."
        )
    return hosts


def _valid_hostname(hostname):
    if not hostname or len(hostname) > 253 or "*" in hostname:
        return False
    normalized = hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(normalized)
        return True
    except ValueError:
        pass
    labels = normalized.split(".")
    return all(
        label
        and len(label) <= 63
        and label[0].isalnum()
        and label[-1].isalnum()
        and all(character.isalnum() or character == "-" for character in label)
        for label in labels
    )


def _origin_hostname_is_allowed(hostname, hosts):
    normalized_hostname = hostname.rstrip(".").lower()
    for allowed_host in hosts:
        try:
            normalized_allowed = urlsplit(f"//{allowed_host}").hostname
        except ValueError:
            continue
        if not normalized_allowed:
            continue
        normalized_allowed = normalized_allowed.rstrip(".").lower()
        if normalized_allowed.startswith("."):
            domain = normalized_allowed[1:]
            if normalized_hostname == domain or normalized_hostname.endswith(f".{domain}"):
                return True
        elif normalized_hostname == normalized_allowed:
            return True
    return False


def _production_csrf_origins(hosts):
    explicit_origins = _csv_environment_value("CSRF_TRUSTED_ORIGINS")
    origins = explicit_origins or [f"https://{host.lstrip('.')}" for host in hosts]
    for origin in origins:
        try:
            parsed_origin = urlsplit(origin)
            hostname = parsed_origin.hostname
            parsed_origin.port
        except ValueError as error:
            raise ImproperlyConfigured(
                "Production CSRF_TRUSTED_ORIGINS contains an invalid origin."
            ) from error
        if (
            parsed_origin.scheme.lower() != "https"
            or not parsed_origin.netloc
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or parsed_origin.path
            or parsed_origin.query
            or parsed_origin.fragment
            or not _valid_hostname(hostname)
            or not _origin_hostname_is_allowed(hostname, hosts)
        ):
            raise ImproperlyConfigured(
                "Production CSRF_TRUSTED_ORIGINS must be HTTPS origins for an allowed host."
            )
    return origins


def _required_postgresql_database(database_url, *, ssl_require):
    from dj_database_url import config as database_config

    try:
        database = database_config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=ssl_require,
        )
    except (TypeError, ValueError):
        raise ImproperlyConfigured("DATABASE_URL is invalid.") from None
    if database.get("ENGINE") != "django.db.backends.postgresql":
        raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL.")
    if any(
        not database.get(field) for field in ("NAME", "HOST", "USER", "PASSWORD")
    ):
        raise ImproperlyConfigured(
            "DATABASE_URL must include a PostgreSQL name, host, user, and password."
        )
    return database


def _is_strong_production_secret(secret):
    if (
        not secret
        or secret == LOCAL_SECRET_KEY
        or secret == "replace-with-a-random-production-secret"
        or secret.lower().startswith("django-insecure-")
        or len(set(secret)) < 5
    ):
        return False

    # A production secret must provide at least 256 bits (32 bytes) of cryptographic key material.
    # 1. Base64-encoded 256-bit secrets (e.g. Render's generateValue: true) decode to at least 32 bytes.
    try:
        normalized = secret.translate(str.maketrans("-_", "+/"))
        padding = "=" * (-len(normalized) % 4)
        decoded = base64.b64decode(normalized + padding, validate=True)
        if len(decoded) >= 32 and len(set(decoded)) >= 5:
            return True
    except (ValueError, binascii.Error):
        pass

    # 2. Text secrets (e.g. Django default 50-character secrets) must have at least 44 characters
    # (the minimum length required to encode 256 bits in 6-bit Base64) with diverse characters.
    if len(secret) >= 44:
        return True

    return False


raw_shelfsum_env = os.environ.get("SHELFSUM_ENV")
if not (raw_shelfsum_env or "").strip() and any(
    os.environ.get(name, "").strip()
    for name in ("DATABASE_URL", "RENDER", "RENDER_EXTERNAL_HOSTNAME")
):
    raise ImproperlyConfigured(
        "SHELFSUM_ENV must be set to production when production signals are present."
    )
SHELFSUM_ENV = (raw_shelfsum_env or "development").strip().lower()

if SHELFSUM_ENV == "production":
    production_secret = os.environ.get("SECRET_KEY", "").strip()
    production_database_url = os.environ.get("DATABASE_URL", "").strip()
    if not production_secret:
        raise ImproperlyConfigured("Production requires SECRET_KEY.")
    if not _is_strong_production_secret(production_secret):
        raise ImproperlyConfigured("Production requires a strong, non-placeholder SECRET_KEY.")
    if not production_database_url:
        raise ImproperlyConfigured("Production requires DATABASE_URL.")

    production_hosts = _production_hosts()
    production_database = _required_postgresql_database(
        production_database_url, ssl_require=True
    )
    production_database["CONN_MAX_AGE"] = 600
    production_database["CONN_HEALTH_CHECKS"] = True
    production_database.setdefault("OPTIONS", {})["sslmode"] = "require"

    SECRET_KEY = production_secret
    DEBUG = False
    ALLOWED_HOSTS = production_hosts
    DATABASES = {"default": production_database}
    CSRF_TRUSTED_ORIGINS = _production_csrf_origins(production_hosts)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }
    if len(production_secret) < 50:
        SILENCED_SYSTEM_CHECKS = ["security.W009"]
elif SHELFSUM_ENV == "postgresql-test":
    if os.environ.get("CI", "").strip().lower() != "true":
        raise ImproperlyConfigured("SHELFSUM_ENV=postgresql-test requires CI=true.")
    test_database_url = os.environ.get("DATABASE_URL", "").strip()
    if not test_database_url:
        raise ImproperlyConfigured(
            "SHELFSUM_ENV=postgresql-test requires DATABASE_URL."
        )
    DATABASES = {
        "default": _required_postgresql_database(
            test_database_url, ssl_require=False
        )
    }
    TEST_RUNNER = "config.test_runner.NoSkipTestRunner"
elif SHELFSUM_ENV not in {
    "",
    "development",
    "local",
}:
    raise ImproperlyConfigured(
        "SHELFSUM_ENV must be development, postgresql-test, or production."
    )
