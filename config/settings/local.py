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

# Print emails to console instead of sending (for local dev)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Set FEEDBACK_EMAIL in env so the view can read it
os.environ.setdefault('FEEDBACK_EMAIL', 'ykshirsagar554@gmail.com')
