import argparse
import secrets
from pathlib import Path

from cryptography.fernet import Fernet


def build(frontend_domain, backend_domain):
    password = secrets.token_urlsafe(32)
    values = {
        'DJANGO_ENV': 'production',
        'DEBUG': 'False',
        'SECRET_KEY': secrets.token_urlsafe(64),
        'ALLOWED_HOSTS': backend_domain,
        'DB_NAME': 'launchplatz',
        'DB_USER': 'launchplatz',
        'DB_PASSWORD': password,
        'DB_HOST': 'db',
        'DB_PORT': '5432',
        'POSTGRES_DB': 'launchplatz',
        'POSTGRES_USER': 'launchplatz',
        'POSTGRES_PASSWORD': password,
        'SMTP_ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'SERVER_CREDENTIAL_ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'GIT_CREDENTIAL_ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'SSH_CONNECTION_TIMEOUT': '30',
        'GIT_OPERATION_TIMEOUT': '120',
        'CELERY_BROKER_URL': 'redis://redis:6379/0',
        'CELERY_RESULT_BACKEND': 'redis://redis:6379/1',
        'DEPLOYMENT_COMMAND_TIMEOUT': '600',
        'DEPLOYMENT_HEALTH_TIMEOUT': '120',
        'DOCKER_ACTION_TIMEOUT': '60',
        'DOCKER_STOP_TIMEOUT': '10',
        'DOCKER_LOG_MAX_LINES': '1000',
        'DOCKER_LOG_MAX_CHARACTERS': '200000',
        'FRONTEND_URL': f'https://{frontend_domain}',
        'CORS_ALLOWED_ORIGINS': f'https://{frontend_domain}',
        'CSRF_TRUSTED_ORIGINS': f'https://{frontend_domain},https://{backend_domain}',
        'SECURE_SSL_REDIRECT': 'True',
        'GUNICORN_WORKERS': '3',
        'GUNICORN_TIMEOUT': '120',
    }
    return '\n'.join(f'{key}={value}' for key, value in values.items()) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frontend-domain', required=True)
    parser.add_argument('--backend-domain', required=True)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    destination = Path('.env.staging')
    if destination.exists() and not args.force:
        print('.env.staging already exists; leaving it unchanged.')
        return
    destination.write_text(
        build(args.frontend_domain, args.backend_domain), encoding='utf-8'
    )
    print('Created .env.staging with private staging credentials.')


if __name__ == '__main__':
    main()
