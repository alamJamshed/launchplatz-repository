import ipaddress

from django.core.exceptions import ValidationError

from projects.validators import validate_compose_service_name


def normalize_hostname(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError('Hostname is required.')
    hostname = value.strip().rstrip('.')
    if any(character in hostname for character in '/:@?#') or '*' in hostname:
        raise ValidationError(
            'Enter a hostname without a scheme, wildcard, port, or path.'
        )
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValidationError('IP addresses cannot be used as hostnames.')
    try:
        ascii_hostname = hostname.encode('idna').decode('ascii').lower()
    except UnicodeError as exc:
        raise ValidationError('Enter a valid international hostname.') from exc
    labels = ascii_hostname.split('.')
    if (
        len(ascii_hostname) > 253
        or len(labels) < 2
        or any(
            not label
            or len(label) > 63
            or label.startswith('-')
            or label.endswith('-')
            or not all(char.isalnum() or char == '-' for char in label)
            for label in labels
        )
    ):
        raise ValidationError('Enter a valid hostname.')
    return ascii_hostname


def validate_service_name(value):
    validate_compose_service_name(value)
    return value

