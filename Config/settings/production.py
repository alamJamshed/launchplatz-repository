from .base import *
from decouple import config

DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()],
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()],
)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Database for production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# SMTP Encryption Key
SMTP_ENCRYPTION_KEY = config('SMTP_ENCRYPTION_KEY')
SERVER_CREDENTIAL_ENCRYPTION_KEY = config('SERVER_CREDENTIAL_ENCRYPTION_KEY')
SSH_CONNECTION_TIMEOUT = config('SSH_CONNECTION_TIMEOUT', default=30, cast=int)
GIT_CREDENTIAL_ENCRYPTION_KEY = config('GIT_CREDENTIAL_ENCRYPTION_KEY')
ENVIRONMENT_VARIABLE_ENCRYPTION_KEY = config(
    'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY'
)
GIT_OPERATION_TIMEOUT = config('GIT_OPERATION_TIMEOUT', default=120, cast=int)
CELERY_BROKER_URL = config('CELERY_BROKER_URL')
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
FRONTEND_URL = config('FRONTEND_URL')
PASSWORD_RESET_TIMEOUT_HOURS = 24

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'file_table': {
            'format': '{levelname:<8} | {asctime} | {module:<15} | {lineno:>4} | {process:>5} | {thread:>10} | {message}\n' + '-' * 100,
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/django_prod.log',
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 5,
            'formatter': 'file_table',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'WARNING',
    },
    'loggers': {
        'coreapp.utils.email_utils': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'api_requests': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
