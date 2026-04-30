from .base import *
import os
import dj_database_url

DEBUG = False


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# --------------------------------------------------------------------------
# Allowed Hosts
# --------------------------------------------------------------------------
# Set ALLOWED_HOSTS via env var (comma-separated).
# Example: ALLOWED_HOSTS=dailyfresh.com,www.dailyfresh.com,web-production-cc730.up.railway.app
# Platform-specific auto-detected hostnames (Render, Railway, etc.) are appended automatically.
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",") if os.getenv("ALLOWED_HOSTS") else []

# Auto-detect platform hostnames
_RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")      # Set by Render
_RAILWAY_HOST = os.getenv("RAILWAY_PUBLIC_DOMAIN")         # Set by Railway
for _host in (_RENDER_HOST, _RAILWAY_HOST):
    if _host and _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

# --------------------------------------------------------------------------
# Database (PostgreSQL via DATABASE_URL — works on any platform)
# --------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=_env_bool("DB_SSL_REQUIRE", default=True),
    )
}

# --------------------------------------------------------------------------
# Cloudinary (Media Storage)
# --------------------------------------------------------------------------
INSTALLED_APPS += [
    "cloudinary",
    "cloudinary_storage",
]

DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": os.getenv("CLOUDINARY_API_KEY"),
    "API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
}

# --------------------------------------------------------------------------
# CSRF Trusted Origins
# --------------------------------------------------------------------------
# Set via env var (comma-separated full URLs).
# Example: CSRF_TRUSTED_ORIGINS=https://dailyfresh.com,https://www.dailyfresh.com
CSRF_TRUSTED_ORIGINS = (
    os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if os.getenv("CSRF_TRUSTED_ORIGINS")
    else []
)

# Auto-add platform hostnames to CSRF trusted origins
for _host in (_RENDER_HOST, _RAILWAY_HOST):
    if _host:
        _origin = f"https://{_host}"
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

# --------------------------------------------------------------------------
# Shiprocket API
# --------------------------------------------------------------------------
SHIPROCKET_ENABLED = os.getenv("SHIPROCKET_ENABLED", "false").lower() == "true"
SHIPROCKET_EMAIL = os.getenv("SHIPROCKET_EMAIL", "")
SHIPROCKET_PASSWORD = os.getenv("SHIPROCKET_PASSWORD", "")
SHIPROCKET_PICKUP_LOCATION = os.getenv("SHIPROCKET_PICKUP_LOCATION", "Home")
SHIPROCKET_WEBHOOK_TOKEN = os.getenv("SHIPROCKET_WEBHOOK_TOKEN", "")
