import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dieta_studencka.settings')

app = Celery('dieta_studencka')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
