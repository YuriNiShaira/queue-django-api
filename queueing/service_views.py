from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from .models import Service, ServiceWindow, Ticket
from .serializers import ServiceSerializer, ServiceWindowSerializer
from drf_spectacular.utils import extend_schema
from .websocket_utils import send_dashboard_update, send_service_update, send_service_status_update

@extend_schema(
    summary="Service List",
    description="Get list of all services (Admin only)",
    tags=['Service Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_list(request):
    #List all services (authenticated users only)
    services = Service.objects.all().order_by('name')
    serializer = ServiceSerializer(services, many=True)
    
    return Response({'success': True,'count': services.count(),'services': serializer.data})


@extend_schema(
    tags=['Service Management'],
    summary='Create service with optional auto-generated windows',
    description='Create a new service and optionally auto-create specified number of windows'
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_service(request):
    """
    Create a service. If num_windows is provided, auto-create that many windows.
    """
    data = request.data.copy()
    num_windows = data.pop('num_windows', None)
    
    serializer = ServiceSerializer(data=data)
    
    if serializer.is_valid():
        service = serializer.save()
        
        windows = []
        if num_windows and int(num_windows) > 0:
            for i in range(1, int(num_windows) + 1):
                window = ServiceWindow.objects.create(
                    service=service,
                    window_number=i,
                    name=f"{service.name} Window {i}",
                    status='active',
                    description=f"Auto-created window for {service.name}"
                )
                windows.append(ServiceWindowSerializer(window).data)
        
        response_data = {
            'success': True,
            'message': f'Service "{service.name}" created successfully',
            'service': ServiceSerializer(service).data
        }
        
        if windows:
            response_data['windows'] = windows
            response_data['message'] += f' with {num_windows} windows'
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    return Response({'success': False,'message': 'Invalid data','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Service List",
    description="Get list of all services (Admin only)",
    tags=['Service Management']
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminUser])
def update_service(request, service_id):
    #Admin-only: Update service
    try:
        service = Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        return Response({'success': False,'message': 'Service not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Track if status is changing
    old_is_active = service.is_active

    serializer = ServiceSerializer(service, data=request.data, partial=True)

    if serializer.is_valid():
        service = serializer.save()

        if old_is_active != service.is_active:
            send_dashboard_update()
            send_service_update(service.id)            
            send_service_status_update(service.id, service.is_active)  

            if not service.is_active:
                # Optionally auto-complete any serving tickets
                Ticket.objects.filter(
                    service=service,
                    status='serving'
                ).update(
                    status='served',
                    served_at=timezone.now()
                )
                
        return Response({'success': True, 'message': f'Service "{service.name}" updated successfully', 'service': serializer.data})
    
    return Response({'success': False, 'message': 'Invalid data', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    summary="Service List",
    description="Get list of all services (Admin only)",
    tags=['Service Management']
)
@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_service(request, service_id):
    #Admin-only: Delete service
    try:
        service = Service.objects.get(id=service_id)
        service_name = service.name
        service.delete()
        
        return Response({'success': True,'message': f'Service "{service_name}" deleted successfully'})
        
    except Service.DoesNotExist:
        return Response({'success': False,'message': 'Service not found'}, status=status.HTTP_404_NOT_FOUND)

@extend_schema(
    summary="Service List",
    description="Get list of all services (Admin only)",
    tags=['Service Management']
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def service_stats(request, service_id):
    # Admin-only: Get service statistics
    try:
        service = Service.objects.get(id=service_id)
        
        today = timezone.now().date()
        tickets_today = service.tickets.filter(ticket_date=today)
        
        stats = {
            'service': ServiceSerializer(service).data,
            'today': {
                'total_tickets': tickets_today.count(),
                'waiting': tickets_today.filter(status__in=['waiting', 'notified']).count(),
                'serving': tickets_today.filter(status='serving').count(),
                'served': tickets_today.filter(status='served').count(),
                'cancelled': tickets_today.filter(status='cancelled').count(),
                'skipped': tickets_today.filter(status='skipped').count(),
            },
            'average_wait_time': service.average_service_time * service.waiting_count
        }
        
        return Response({'success': True,'stats': stats})
        
    except Service.DoesNotExist:
        return Response({'success': False,'message': 'Service not found'}, status=status.HTTP_404_NOT_FOUND)