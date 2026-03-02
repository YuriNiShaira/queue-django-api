"""
ASGI config for backend project.
"""

import os
import django
from django.core.asgi import get_asgi_application

# Set the settings module FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django.setup()  # This is the key line that was missing!

# Now import channels and routing AFTER django.setup()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from queueing import routing as queueing_routing

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            queueing_routing.websocket_urlpatterns
        )
    ),
})