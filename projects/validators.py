import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


SCP_GIT_URL = re.compile(
    r'^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:[A-Za-z0-9._~/-]+$'
)


def validate_git_repository_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError('Git repository URL is required.')

    value = value.strip()
    if SCP_GIT_URL.fullmatch(value):
        return

    parsed = urlsplit(value)
    if parsed.scheme not in {'https', 'ssh'}:
        raise ValidationError(
            'Use an HTTPS, ssh://, or git@host:path repository URL.'
        )
    if not parsed.hostname or not parsed.path or parsed.path == '/':
        raise ValidationError('Git repository URL must include a host and path.')
    if parsed.password or (parsed.scheme == 'https' and parsed.username):
        raise ValidationError('Repository credentials must not be embedded in the URL.')
    if parsed.query or parsed.fragment:
        raise ValidationError('Repository URL must not contain a query or fragment.')


def normalize_and_validate_domain(value):
    if not value:
        return ''
    value = value.strip().lower().rstrip('.')
    if any(character in value for character in '/:@?#'):
        raise ValidationError('Enter a domain without a scheme, port, or path.')
    try:
        URLValidator(schemes=['https'])(f'https://{value}')
    except ValidationError as exc:
        raise ValidationError('Enter a valid domain name.') from exc
    return value


def validate_docker_compose_path(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError('Docker Compose path is required.')
    value = value.strip()
    if '\\' in value:
        raise ValidationError('Docker Compose path must use forward slashes.')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValidationError(
            'Docker Compose path must be relative and cannot contain "..".'
        )
    if value in {'.', './'} or value.endswith('/'):
        raise ValidationError('Docker Compose path must point to a file.')


def validate_environment_variables(value):
    """Legacy validator retained for historical Project migrations."""
    if not isinstance(value, dict):
        raise ValidationError('Environment variables must be a JSON object.')
    if not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValidationError('Environment variable keys and values must be strings.')


ENVIRONMENT_KEY_PATTERN = re.compile(r'^[A-Z_][A-Z0-9_]*$')
COMPOSE_SERVICE_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$')


def validate_environment_variable_key(value):
    if not value or not ENVIRONMENT_KEY_PATTERN.fullmatch(value):
        raise ValidationError(
            'Use uppercase letters, digits, and underscores; the first character '
            'must be a letter or underscore.'
        )


def validate_compose_service_name(value):
    if not value or len(value) > 100 or not COMPOSE_SERVICE_PATTERN.fullmatch(value):
        raise ValidationError('Enter a valid Docker Compose service name.')
