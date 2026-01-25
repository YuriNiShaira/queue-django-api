from django.urls import path
from .views import ServiceListView, GenerateTicketView

app_name = 'queueing'

urlpatterns = [
    path('services/', ServiceListView.as_view(), name='service-list'),
    path('tickets/generate/', GenerateTicketView.as_view(), name='generate-ticket'),
]