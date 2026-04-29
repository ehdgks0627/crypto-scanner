import os
from urllib.parse import urlparse
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_csv("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "")

if not DEBUG and SECRET_KEY == "dev-only-secret-key":
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=false.")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "apps.agents",
    "apps.assets",
    "apps.core",
    "apps.dashboard",
    "apps.discoveries",
    "apps.health",
    "apps.jobs",
    "apps.meta",
    "apps.risk",
    "apps.snapshots",
    "apps.targets",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.HostValidationMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "apps.core.middleware.APIKeyMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pqc_ras.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    parsed_database_url = urlparse(DATABASE_URL)
    if parsed_database_url.scheme.startswith("postgres"):
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": parsed_database_url.path.removeprefix("/"),
                "USER": parsed_database_url.username or "",
                "PASSWORD": parsed_database_url.password or "",
                "HOST": parsed_database_url.hostname or "",
                "PORT": parsed_database_url.port or "",
            }
        }
    elif parsed_database_url.scheme == "sqlite":
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": parsed_database_url.path,
            }
        }
    else:
        raise RuntimeError(f"Unsupported DATABASE_URL scheme: {parsed_database_url.scheme}")
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

USE_TZ = True
TIME_ZONE = "Asia/Seoul"

DEFAULT_AGENT_BOOTSTRAP_TOKEN = "dev-bootstrap-token"
AGENT_BOOTSTRAP_TOKEN = os.environ.get("AGENT_BOOTSTRAP_TOKEN", DEFAULT_AGENT_BOOTSTRAP_TOKEN)
API_AUTH_TOKEN = os.environ.get("API_AUTH_TOKEN", "")

if not DEBUG:
    if not API_AUTH_TOKEN:
        raise RuntimeError("API_AUTH_TOKEN must be set when DJANGO_DEBUG=false.")
    if not AGENT_BOOTSTRAP_TOKEN or AGENT_BOOTSTRAP_TOKEN == DEFAULT_AGENT_BOOTSTRAP_TOKEN:
        raise RuntimeError("AGENT_BOOTSTRAP_TOKEN must be set to a non-default value when DJANGO_DEBUG=false.")
    if not ALLOWED_HOSTS:
        raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG=false.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.environ.get("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
X_FRAME_OPTIONS = os.environ.get("DJANGO_X_FRAME_OPTIONS", "DENY")
CSRF_TRUSTED_ORIGINS = env_csv("DJANGO_CSRF_TRUSTED_ORIGINS")

LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "apps.core.logging.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
