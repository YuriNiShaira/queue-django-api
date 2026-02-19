from django.urls import path
from . import auth_views

app_name = 'auth'

urlpatterns = [
    # Public auth endpoints
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('refresh/', auth_views.refresh_token_view, name='refresh-token'),
    
    # Authenticated user endpoints
    path('me/', auth_views.current_user_view, name='current-user'),
    path('change-password/', auth_views.change_password_view, name='change-password'),
    
    # Admin management endpoints
    path('admin/staff/create/', auth_views.create_staff_view, name='create-staff'),
    path('admin/staff/list/', auth_views.list_staff_view, name='list-staff'),
    path('admin/staff/<int:user_id>/delete/', auth_views.delete_staff_view, name='delete-staff'),
    path('admin/staff/<int:user_id>/update/', auth_views.update_staff_view, name='update-staff'),
    path('admin/staff/<int:user_id>/assign-service/', auth_views.assign_staff_to_service, name='assign-staff-service'),
]