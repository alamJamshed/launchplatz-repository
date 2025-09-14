from .base import *
from decouple import config

DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])

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
