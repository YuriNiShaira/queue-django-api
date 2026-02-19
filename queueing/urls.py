from django.urls import path, include
from . import views, staff_views, window_views, auth_views, service_views, analytics_views

app_name = 'queueing'

urlpatterns = [
    # Auth endpoints
    path('auth/', include('queueing.auth_urls')),
    
    # Public endpoints
    path('services/public/', views.public_service_list, name='public-service-list'),
    path('tickets/generate/', views.generate_ticket, name='generate-ticket'),
    path('tickets/<uuid:ticket_id>/status/', views.ticket_status, name='ticket-status'),
    path('dashboard/status/', views.dashboard_status, name='dashboard-status'),
    
    # Service management (Admin only)
    path('services/', service_views.service_list, name='service-list'),
    path('services/create/', service_views.create_service, name='create-service'),
    path('services/<int:service_id>/update/', service_views.update_service, name='update-service'),
    path('services/<int:service_id>/delete/', service_views.delete_service, name='delete-service'),
    path('services/<int:service_id>/stats/', service_views.service_stats, name='service-stats'),
    
    # Service Window management
    path('services/<int:service_id>/windows/', window_views.service_windows_list, name='service-windows-list'),
    path('services/<int:service_id>/windows/create/', window_views.create_service_window, name='create-service-window'),
    path('windows/<int:window_id>/update/', window_views.update_service_window, name='update-service-window'),
    path('windows/<int:window_id>/delete/', window_views.delete_service_window, name='delete-service-window'),
    
    # Staff queue management
    path('staff/dashboard/', staff_views.staff_dashboard, name='staff-dashboard'),
    path('staff/call-next/', staff_views.call_next_ticket, name='call-next-ticket'),
    path('staff/call-specific/', staff_views.call_specific_ticket, name='call-specific-ticket'),
    path('staff/toggle-queue/', staff_views.toggle_queue_status, name='toggle-queue'),
    path('staff/tickets/<uuid:ticket_id>/start/', staff_views.start_serving, name='start-serving'),
    path('staff/tickets/<uuid:ticket_id>/complete/', staff_views.complete_serving, name='complete-serving'),
    path('staff/tickets/<uuid:ticket_id>/remove/', staff_views.remove_ticket, name='remove-ticket'),
    path('staff/tickets/<uuid:ticket_id>/recall/', staff_views.recall_ticket, name='recall-ticket'),

    # NEW: Analytics endpoints
    path('admin/analytics/', analytics_views.admin_analytics, name='admin-analytics'),
    path('admin/analytics/service/<int:service_id>/', analytics_views.service_analytics, name='service-analytics'),
]