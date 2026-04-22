"""
ASGI config for dieta_studencka project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import dieta_studencka.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dieta_studencka.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
	{
		'http': django_asgi_app,
		'websocket': AuthMiddlewareStack(
			URLRouter(dieta_studencka.routing.websocket_urlpatterns)
		),
	}
)
