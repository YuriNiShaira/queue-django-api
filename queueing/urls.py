from django.urls import path
from . import views

app_name = 'queueing'

urlpatterns = [
    path('windows/', views.window_list, name='window-list'),
    path('tickets/generate/', views.generate_ticket, name='generate-ticket'),
    path('tickets/<uuid:ticket_id>/status/', views.ticket_status, name='ticket-status'),
    path('services/status/', views.service_status, name='service-status'),
]