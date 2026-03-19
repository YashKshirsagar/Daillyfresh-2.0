from .base import *
import os
import dj_database_url

DEBUG = False

ALLOWED_HOSTS = ["*"]  # temporary, we’ll tighten later
 
# Production Database (PostgreSQL)
# ✅ Railway PostgreSQL (via DATABASE_URL)
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

INSTALLED_APPS += [
    "cloudinary",
    "cloudinary_storage",
]

# Media storage → Cloudinary
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# Cloudinary credentials (from Railway env vars)
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": os.getenv("CLOUDINARY_API_KEY"),
    "API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
}
## Used for production, to allow CSRF from our deployed frontend URL-admin page forbidden error
CSRF_TRUSTED_ORIGINS = ["https://welcoming-vibrancy-production.up.railway.app"]