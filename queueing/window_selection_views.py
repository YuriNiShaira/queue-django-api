from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import ServiceWindow
from .serializers import ServiceWindowSerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def select_window(request):
    """
    Staff selects which window they're manning
    This should be called immediately after login
    """
    window_id = request.data.get('window_id')
    if not window_id:
        return Response({'success':'False', 'message': 'window_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not hasattr(request.user, 'staff_profile'):
        return Response({'success': False, 'message': 'User is not a staff member'}, status=status.HTTP_403_FORBIDDEN)
    
    staff_profile = request.user.staff_profile

    if not staff_profile.assigned_service:
        return Response({'success': False, 'message':'no service assigned to your account'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        #Get the window and verify it belongs to staff's service
        window = ServiceWindow.objects.get(id=window_id, service=staff_profile.assigned_service, status='active')
    except ServiceWindow.DoesNotExist:
        return Response({'success': False, 'message': 'Window not found, inactive, or not part of your service'},status=status.HTTP_404_NOT_FOUND)
    
    # Check if window is already manned by someone else
    if window.current_staff and window.current_staff != request.user:
        return Response({'success': False,'message': f'This window is already being manned by {window.current_staff.username}'}, status=status.HTTP_400_BAD_REQUEST)
    
    window.assign_staff(request.user)

    return Response({
        'success': True,
        'message': f'You are now manning {window.name}',
        'window': ServiceWindowSerializer(window).data,
        'service': {
            'id': staff_profile.assigned_service.id,
            'name': staff_profile.assigned_service.name,
            'prefix': staff_profile.assigned_service.prefix
        }
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def release_window(request):
    #Staff releases current window (before logout or switching)
    if not hasattr(request.user, 'staff_profile'):
        return Response({'success':False, 'message':'User is not a staff'}, status=status.HTTP_403_FORBIDDEN)
    
    staff_profile = request.user.staff_profile

    if staff_profile.current_window:
        window_name = staff_profile.current_window.name
        staff_profile.clear_current_window()
        
        # Update logout time
        staff_profile.last_logout_at = timezone.now()
        staff_profile.save()

        return Response({'success': True,'message': f'Released {window_name}'})
    
    return Response({'success': True,'message': 'No window was assigned'})