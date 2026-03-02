from django.urls import re_path, path
from . import consumers

websocket_urlpatterns = [
        path('ws/test/', consumers.TestConsumer.as_asgi()),
    re_path(r'^ws/dashboard/$', consumers.DashboardConsumer.as_asgi()),
    re_path(r'^ws/staff/(?P<service_id>\d+)/$', consumers.StaffDashboardConsumer.as_asgi()),
    re_path(r'^ws/ticket/(?P<ticket_id>[0-9a-f-]+)/$', consumers.TicketStatusConsumer.as_asgi()),
]