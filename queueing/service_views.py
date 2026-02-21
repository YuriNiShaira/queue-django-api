from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from time import timezone
from .models import Service
from .serializers import ServiceSerializer
from drf_spectacular.utils import extend_schema

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
    summary="Service List",
    description="Get list of all services (Admin only)",
    tags=['Service Management']
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_service(request):
    #Admin-only: Create new service
    serializer = ServiceSerializer(data=request.data)
    
    if serializer.is_valid():
        service = serializer.save()
        
        return Response({'success': True,'message': f'Service "{service.name}" created successfully','service': ServiceSerializer(service).data}, status=status.HTTP_201_CREATED)
    
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
    
    serializer = ServiceSerializer(service, data=request.data, partial=True)
    
    if serializer.is_valid():
        service = serializer.save()
        
        return Response({'success': True,'message': f'Service "{service.name}" updated successfully','service': serializer.data})
    
    return Response({'success': False,'message': 'Invalid data','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

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