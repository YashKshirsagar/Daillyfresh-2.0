from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

from .base import *

# Development mein Debug ON rahega
DEBUG = True

ALLOWED_HOSTS = ['*']

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "local-dev-secret-key-change-me"
)
# Development Database (SQLite)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
NPM_BIN_PATH = r"C:\nvm4w\nodejs\npm.cmd" 

# Email config for local testing (SMTP via Gmail)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Set FEEDBACK_EMAIL in env so the view can read it
os.environ.setdefault('FEEDBACK_EMAIL', os.getenv('FEEDBACK_EMAIL', ''))

# Shiprocket API
SHIPROCKET_ENABLED = os.getenv("SHIPROCKET_ENABLED", "false").lower() == "true"
SHIPROCKET_EMAIL = os.getenv("SHIPROCKET_EMAIL", "")
SHIPROCKET_PASSWORD = os.getenv("SHIPROCKET_PASSWORD", "")
SHIPROCKET_PICKUP_LOCATION = os.getenv("SHIPROCKET_PICKUP_LOCATION", "Home")
SHIPROCKET_WEBHOOK_TOKEN = os.getenv("SHIPROCKET_WEBHOOK_TOKEN", "")
