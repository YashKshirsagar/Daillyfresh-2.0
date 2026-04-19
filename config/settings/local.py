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
EMAIL_HOST_USER = 'ykshirsagar554@gmail.com'
EMAIL_HOST_PASSWORD = 'mcdb tjof sdpe qczg'
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Set FEEDBACK_EMAIL in env so the view can read it
os.environ.setdefault('FEEDBACK_EMAIL', 'ykshirsagar554@gmail.com')
