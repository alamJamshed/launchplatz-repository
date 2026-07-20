from decouple import config

environment = config('DJANGO_ENV', default='development')

if environment == 'production':
    from .production import *
elif environment == 'test':
    from .test import *
else:
    from .development import *
