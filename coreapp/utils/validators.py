from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re

def validate_phone_number(value):
    """Validate phone number format"""
    phone_regex = re.compile(r'^\+?1?\d{9,15}$')
    if not phone_regex.match(value):
        raise ValidationError(_('Invalid phone number format'))

def validate_postal_code(value):
    """Validate postal code format"""
    if not re.match(r'^[A-Za-z0-9\s-]{3,10}$', value):
        raise ValidationError(_('Invalid postal code format'))