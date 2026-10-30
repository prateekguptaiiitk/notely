"""Django settings for Notely."""

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
RUNNING_DEV_SERVER = len(sys.argv) > 1 and sys.argv[1] == "runserver"


def load_local_env():
    """Load .env for local development; explicit shell variables take priority."""
    env_file = BASE_DIR / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_local_env()
SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-local-key-change-before-deploy")
DEBUG = os.environ.get("DEBUG", "0").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
CSRF_TRUSTED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if RENDER_EXTERNAL_HOSTNAME:
    render_origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)
ADMIN_URL = os.environ.get("ADMIN_URL", "admin/").strip("/") + "/"
PRIVATE_STORAGE_VALUE = Path(
    os.environ.get("PRIVATE_STORAGE_DIR", str(BASE_DIR.parent / "notely-private-storage"))
).expanduser()
if not PRIVATE_STORAGE_VALUE.is_absolute():
    PRIVATE_STORAGE_VALUE = BASE_DIR / PRIVATE_STORAGE_VALUE
PRIVATE_STORAGE_DIR = PRIVATE_STORAGE_VALUE.resolve()
PRIVATE_STORAGE_BACKEND = os.environ.get("PRIVATE_STORAGE_BACKEND", "local").lower()
if PRIVATE_STORAGE_BACKEND not in {"local", "s3"}:
    raise RuntimeError("PRIVATE_STORAGE_BACKEND must be 'local' or 's3'")
PRIVATE_S3_ENDPOINT_URL = os.environ.get("PRIVATE_S3_ENDPOINT_URL", "").strip()
PRIVATE_S3_REGION = os.environ.get("PRIVATE_S3_REGION", "").strip()
PRIVATE_S3_BUCKET = os.environ.get("PRIVATE_S3_BUCKET", "").strip()
PRIVATE_S3_ACCESS_KEY_ID = os.environ.get("PRIVATE_S3_ACCESS_KEY_ID", "").strip()
PRIVATE_S3_SECRET_ACCESS_KEY = os.environ.get("PRIVATE_S3_SECRET_ACCESS_KEY", "").strip()
if PRIVATE_STORAGE_BACKEND == "s3" and not all(
    (
        PRIVATE_S3_ENDPOINT_URL,
        PRIVATE_S3_REGION,
        PRIVATE_S3_BUCKET,
        PRIVATE_S3_ACCESS_KEY_ID,
        PRIVATE_S3_SECRET_ACCESS_KEY,
    )
):
    raise RuntimeError("S3 private storage needs endpoint, region, bucket, and credentials")
WEB_ROOTS = [
    (BASE_DIR / "static").resolve(),
    (BASE_DIR / "media").resolve(),
    (BASE_DIR / "staticfiles").resolve(),
]
if any(PRIVATE_STORAGE_DIR == path or path in PRIVATE_STORAGE_DIR.parents for path in WEB_ROOTS):
    raise RuntimeError("PRIVATE_STORAGE_DIR must be outside static and media roots")

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "15"))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "60"))
MAX_IMAGE_DIMENSION = 1600
SINGLE_SESSION_POLICY = os.environ.get("SINGLE_SESSION_POLICY", "replace").lower()
if SINGLE_SESSION_POLICY not in {"replace", "block"}:
    raise RuntimeError("SINGLE_SESSION_POLICY must be 'replace' or 'block'")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts.apps.AccountsConfig",
    "notes.apps.NotesConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "config.middleware.LocalAdminOriginMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "accounts.middleware.ActiveSingleSessionMiddleware",
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
                "accounts.context_processors.viewer_context",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_CONN_MAX_AGE = int(os.environ.get("DB_CONN_MAX_AGE", "60"))
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    parsed_db = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed_db.path.lstrip("/")),
            "USER": unquote(parsed_db.username or ""),
            "PASSWORD": unquote(parsed_db.password or ""),
            "HOST": parsed_db.hostname or "",
            "PORT": parsed_db.port or 5432,
            "CONN_MAX_AGE": DB_CONN_MAX_AGE,
            "OPTIONS": {"sslmode": os.environ.get("PGSSLMODE", "prefer")},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "CONN_MAX_AGE": DB_CONN_MAX_AGE,
        }
    }

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 900,
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or RUNNING_DEV_SERVER
            else "whitenoise.storage.CompressedStaticFilesStorage"
        )
    },
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "notes:list"
LOGOUT_REDIRECT_URL = "login"
SESSION_ENGINE = (
    "django.contrib.sessions.backends.cached_db"
    if REDIS_URL
    else "django.contrib.sessions.backends.db"
)
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG and not RUNNING_DEV_SERVER
CSRF_COOKIE_SECURE = not DEBUG and not RUNNING_DEV_SERVER
SECURE_SSL_REDIRECT = not DEBUG and not RUNNING_DEV_SERVER
SECURE_HSTS_SECONDS = 31_536_000 if not DEBUG and not RUNNING_DEV_SERVER else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG and not RUNNING_DEV_SERVER
SECURE_HSTS_PRELOAD = not DEBUG and not RUNNING_DEV_SERVER
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
X_FRAME_OPTIONS = "DENY"
if os.environ.get("RENDER", "").lower() == "true":
    # Render terminates TLS at its load balancer and forwards this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
