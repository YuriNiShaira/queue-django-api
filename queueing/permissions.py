from rest_framework.permissions import BasePermission

class IsServiceStaff(BasePermission):
    # Permission check for staff assigned to a specific service
    def has_permission(self, request, view):
        # Allow admin users
        if request.user.is_superuser:
            return True
        
        # Check if user is staff
        if not request.user.is_staff:
            return False
        
        # Check if user has staff profile
        if not hasattr(request.user, 'staff_profile'):
            return False
        
        # Staff must be assigned to a service
        return request.user.staff_profile.assigned_service is not None

class HasServicePermission(BasePermission):
    # Permission check for specific service access

    def has_object_permission(self, request, view, obj):
        # Allow admin users
        if request.user.is_superuser:
            return True
        
        # Get staff's assigned service
        staff_profile = getattr(request.user, 'staff_profile', None)
        if not staff_profile or not staff_profile.assigned_service:
            return False
        
        # Check if object belongs to staff's assigned service
        if hasattr(obj, 'service'):
            return obj.service == staff_profile.assigned_service
        elif hasattr(obj, 'assigned_service'):
            return obj.assigned_service == staff_profile.assigned_service
        
        return False