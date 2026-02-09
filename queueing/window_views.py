from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Service, ServiceWindow
from .serializers import ServiceWindowSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes


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
    summary="Service Windows List",
    description="Get list of windows for a service",
    tags=['Service Window Management']
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminUser])
def update_service_window(request, window_id):
    #Admin-only: Update service window
    try:
        window = ServiceWindow.objects.get(id=window_id)
    except ServiceWindow.DoesNotExist:
        return Response({'success': False, 'message': 'Window not found' }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = ServiceWindowSerializer(window, data=request.data, partial=True)

    if serializer.is_valid():
        window = serializer.save()

        return Response({'success': True, 'message':f'Window updated successfully', 'window':serializer.data})
    
    return Response({'success': False, 'message': 'Invalid data', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    summary="Service Windows List",
    description="Get list of windows for a service",
    tags=['Service Window Management']
)
@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_service_window(request, window_id):
    # Admin-only: Delete service window
    try:
        window = ServiceWindow.objects.get(id=window_id)
        window_name = window.name or f"Window {window.window_number}"
        service_name = window.service.name
        window.delete()
        
        return Response({'success': True,'message': f'Window "{window_name}" deleted from {service_name}'})
        
    except ServiceWindow.DoesNotExist:
        return Response({'success': False,'message': 'Window not found'}, status=status.HTTP_404_NOT_FOUND)
