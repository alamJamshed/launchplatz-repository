from django.utils.text import slugify
from django.utils import timezone
import uuid

def generate_unique_slug(model_class, title, slug_field='slug'):
    """Generate unique slug for model"""
    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    
    while model_class.objects.filter(**{slug_field: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    return slug

def generate_uuid():
    """Generate UUID string"""
    return str(uuid.uuid4())

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip