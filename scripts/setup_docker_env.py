import argparse
import base64
import secrets
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / '.env.docker'


def generate_fernet_key():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def generate_values():
    database_password = secrets.token_urlsafe(24)
    return {
        'DJANGO_ENV': 'development',
        'DEBUG': 'True',
        'SECRET_KEY': secrets.token_urlsafe(48),
        'ALLOWED_HOSTS': 'localhost,127.0.0.1,web',
        'DB_NAME': 'launchplatz',
        'DB_USER': 'launchplatz',
        'DB_PASSWORD': database_password,
        'DB_HOST': 'db',
        'DB_PORT': '5432',
        'POSTGRES_DB': 'launchplatz',
        'POSTGRES_USER': 'launchplatz',
        'POSTGRES_PASSWORD': database_password,
        'SMTP_ENCRYPTION_KEY': generate_fernet_key(),
        'SERVER_CREDENTIAL_ENCRYPTION_KEY': generate_fernet_key(),
        'GIT_CREDENTIAL_ENCRYPTION_KEY': generate_fernet_key(),
        'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY': generate_fernet_key(),
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
        'FRONTEND_URL': 'http://localhost:3000',
        'CORS_ALLOWED_ORIGINS': 'http://localhost:3000,http://127.0.0.1:3000',
        'SECURE_SSL_REDIRECT': 'False',
    }


def render_environment(values):
    return ''.join(f'{key}={value}\n' for key, value in values.items())


def write_environment(output=DEFAULT_OUTPUT, force=False):
    output = Path(output)
    if output.exists() and not force:
        return False
    output.write_text(render_environment(generate_values()), encoding='utf-8')
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Generate private local credentials for Docker development.'
    )
    parser.add_argument('--force', action='store_true', help='replace an existing file')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    created = write_environment(args.output, force=args.force)
    if created:
        print(f'Created {args.output}')
    else:
        print(f'Preserved existing {args.output}; use --force to replace it.')


if __name__ == '__main__':
    main()
