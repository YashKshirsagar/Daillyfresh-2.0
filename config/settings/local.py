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
