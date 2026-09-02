"""Django settings for CNVMaster."""
from pathlib import Path
import os
import tempfile

from cnvmaster.template_dirs import extract_template_dirs

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-local-development-only')
DEBUG = os.getenv('DEBUG', '1').lower() in {'1', 'true', 'yes'}
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'state_manager.apps.StateManagerConfig',
    'protein.apps.ProteinConfig', 'goterm.apps.GoTermConfig',
    'drug_master.apps.DrugMasterConfig', 'product', 'file_master',
    'infrastructure', 'user', 'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'cnvmaster.middleware.RequestResponseMiddleware',
    'state_manager.middleware.StateCaptureMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cnvmaster.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    # BASE_DIR preserves full component include paths; discovered leaf dirs allow basename lookup.
    'DIRS': [BASE_DIR, *extract_template_dirs(BASE_DIR)],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'cnvmaster.wsgi.application'
RUNTIME_DATA_ROOT = Path(os.getenv('CNVMASTER_STATE_ROOT', Path(tempfile.gettempdir()) / 'stemgraph'))
RUNTIME_DATA_ROOT.mkdir(parents=True, exist_ok=True)
if os.getenv('DJANGO_DB_ENGINE', 'postgresql') == 'sqlite':
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DJANGO_DATABASE_PATH', str(RUNTIME_DATA_ROOT / 'db.sqlite3')),
    }}
else:
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'stemgraph'),
        'USER': os.getenv('POSTGRES_USER', 'stemgraph'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'stemgraph-local'),
        'HOST': os.getenv('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('POSTGRES_CONN_MAX_AGE', '60')),
        'OPTIONS': {'connect_timeout': int(os.getenv('POSTGRES_CONNECT_TIMEOUT', '5'))},
    }}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.LighterUser'
