import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Config.settings')

app = Celery('launchplatz')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
