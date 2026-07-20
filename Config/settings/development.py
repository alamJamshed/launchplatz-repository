from .base import *
from decouple import config
DEBUG = config('DEBUG', default=True, cast=bool)
SECRET_KEY = config('SECRET_KEY', default='django-insecure-!kz%=&p7$llq@lj2s)slkp()!vtfw$ms=fj=w9z85k5^f-to4$')
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default=5432, cast=int),
    }
}

# CORS settings for development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# SMTP Encryption Key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SMTP_ENCRYPTION_KEY = config('SMTP_ENCRYPTION_KEY', default=None)

# Required before server credentials can be stored or used.
SERVER_CREDENTIAL_ENCRYPTION_KEY = config(
    'SERVER_CREDENTIAL_ENCRYPTION_KEY', default=None
)
SSH_CONNECTION_TIMEOUT = config('SSH_CONNECTION_TIMEOUT', default=30, cast=int)
GIT_CREDENTIAL_ENCRYPTION_KEY = config(
    'GIT_CREDENTIAL_ENCRYPTION_KEY', default=None
)
ENVIRONMENT_VARIABLE_ENCRYPTION_KEY = config(
    'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY', default=None
)
GIT_OPERATION_TIMEOUT = config('GIT_OPERATION_TIMEOUT', default=120, cast=int)
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=None)
CELERY_RESULT_BACKEND = config(
    'CELERY_RESULT_BACKEND', default=CELERY_BROKER_URL
)
DEPLOYMENT_COMMAND_TIMEOUT = config(
    'DEPLOYMENT_COMMAND_TIMEOUT', default=600, cast=int
)
DEPLOYMENT_HEALTH_TIMEOUT = config(
    'DEPLOYMENT_HEALTH_TIMEOUT', default=120, cast=int
)
DOCKER_ACTION_TIMEOUT = config('DOCKER_ACTION_TIMEOUT', default=60, cast=int)
DOCKER_STOP_TIMEOUT = config('DOCKER_STOP_TIMEOUT', default=10, cast=int)
DOCKER_LOG_MAX_LINES = config('DOCKER_LOG_MAX_LINES', default=1000, cast=int)
DOCKER_LOG_MAX_CHARACTERS = config(
    'DOCKER_LOG_MAX_CHARACTERS', default=200000, cast=int
)

# Frontend URL for email links
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')
PASSWORD_RESET_TIMEOUT_HOURS = 24

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'file_table': {
            'format': '{levelname:<8} | {asctime} | {module:<15} | {lineno:>4} | {process:>5} | {thread:>10} | {message}\n' + '-' * 100,
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/django_dev.log',
            'formatter': 'file_table',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'ERROR',
    },
    'loggers': {
        'coreapp.utils.email_utils': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'api_requests': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
