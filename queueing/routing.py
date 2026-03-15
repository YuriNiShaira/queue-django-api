from django.urls import re_path, path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/dashboard/$', consumers.DashboardConsumer.as_asgi()),
    re_path(r'^ws/staff/(?P<service_id>\d+)/$', consumers.StaffDashboardConsumer.as_asgi()),
    re_path(r'^ws/service/(?P<service_id>\d+)/windows/$', consumers.WindowStatusConsumer.as_asgi()),
    re_path(r'^ws/ticket/(?P<ticket_id>[0-9a-f-]+)/$', consumers.TicketStatusConsumer.as_asgi()),
    re_path(r'^ws/window/(?P<window_id>\d+)/$', consumers.WindowConsumer.as_asgi()),
    re_path(r'^ws/service/(?P<service_id>\d+)/status/$', consumers.ServiceStatusConsumer.as_asgi()),
]