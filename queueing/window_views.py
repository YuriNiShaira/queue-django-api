from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Service, ServiceWindow, Ticket
from .serializers import ServiceWindowSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .websocket_utils import send_dashboard_update, send_service_update, send_service_status_update, send_ticket_update
from django.utils import timezone



@extend_schema(
    summary="Service Windows List",
    description="Get list of windows for a service",
    tags=['Service Window Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_windows_list(request, service_id):
    # Get all windows for a specific service
    try:
        service = Service.objects.get(id=service_id)
        windows = service.windows.all().order_by('window_number')
        serializer = ServiceWindowSerializer(windows, many=True)

        return Response({'success': True, 'service': service.name, 'count': windows.count(), 'windows': serializer.data})
    
    except Service.DoesNotExist:
        return Response({'success': False, 'message':'Service not found'}, status=404)


@extend_schema(
    summary="Service Windows List",
    description="Get list of windows for a service",
    tags=['Service Window Management']
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_service_window(request, service_id):
    #Admin-only: Create new window for a service
    try:
        service = Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        return Response({'success': False, 'message':'Service not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Add service to request data
    data = request.data.copy()
    data['service'] = service_id

    serializer = ServiceWindowSerializer(data=data)

    if serializer.is_valid():
        window = serializer.save()

        return Response({
            'success': True,
            'message': f'Window "{window.name or f"Window {window.window_number}"}" created for {service.name}',
            'window': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    return Response({'success': False,'message': 'Invalid data','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Service Window Management'],
    summary='Update service window status',
    description='Update window status and automatically update parent service active status'
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminUser])
def update_service_window(request, window_id):
    """
    Update service window. When status changes, automatically update parent service.
    """
    try:
        window = ServiceWindow.objects.get(id=window_id)
    except ServiceWindow.DoesNotExist:
        return Response({'success': False, 'message': 'Window not found'}, status=status.HTTP_404_NOT_FOUND)
    
    old_status = window.status
    serializer = ServiceWindowSerializer(window, data=request.data, partial=True)
    
    if serializer.is_valid():
        window = serializer.save()
        
        #If window becoming inactive, complete its current serving ticket
        completed_ticket = None
        if old_status == 'active' and window.status == 'inactive':
            current_ticket = Ticket.objects.filter(assigned_window=window, status='serving').first()

            if current_ticket:
                current_ticket.status = 'served'
                current_ticket.served_at = timezone.now()
                current_ticket.save()
                completed_ticket = current_ticket.display_number

                send_ticket_update(str(current_ticket.ticket_id))

        
        # Check if status actually changed
        if old_status != window.status:
            # Update service active status based on window availability
            service_updated = window.service.update_active_status()
            
            send_dashboard_update()
            send_service_update(window.service.id)
            
            if service_updated:
                send_service_status_update(window.service.id, window.service.is_active)
        
        response_data = {
            'success': True,
            'message': f'Window updated successfully',
            'window': serializer.data,
            'service_active': window.service.is_active
        }
        
        if completed_ticket:
            response_data['message'] += f' and completed ticket {completed_ticket}'
            response_data['completed_ticket'] = completed_ticket
        
        return Response(response_data)
    
    return Response({'success': False, 'message': 'Invalid data', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Service Windows List",
    description="Get list of windows for a service",
    tags=['Service Window Management']
)
@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_service_window(request, window_id):
    #Delete window and update service status
    try:
        window = ServiceWindow.objects.get(id=window_id)
        service = window.service
        window_name = window.name or f"Window {window.window_number}"
        service_name = service.name
        
        current_ticket = Ticket.objects.filter(assigned_window=window, status='serving').first()

        if current_ticket:
            current_ticket.status = 'served'
            current_ticket.served_at = timezone.now()
            current_ticket.save()

            send_ticket_update(str(current_ticket.ticket_id))


        window.delete()
        
        # Update service active status
        service_updated = service.update_active_status()
        
        send_dashboard_update()
        send_service_update(service.id)
        if service_updated:
            send_service_status_update(service.id, service.is_active)
        
        return Response({'success': True, 'message': f'Window "{window_name}" deleted from {service_name}', 'service_active': service.is_active})
        
    except ServiceWindow.DoesNotExist:
        return Response({'success': False, 'message': 'Window not found'}, status=404)
