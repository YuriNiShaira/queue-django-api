from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from .models import Service, Ticket
from .serializers import ServiceSerializer, TicketSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes



@extend_schema(
    summary="Generate Ticket",
    description="Generate a new ticket for a specific service",
    tags=['Public Endpoints']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def public_service_list(request):
    # Public: Get active services for ticket generation
    services = Service.objects.filter(is_active=True).order_by('name')
    serializer = ServiceSerializer(services, many=True)
    
    return Response({'success': True,'count': services.count(),'services': serializer.data})

@extend_schema(
    summary="Generate Ticket",
    description="Generate a new ticket for a specific service",
    tags=['Public Endpoints']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def generate_ticket(request):
    # Public: Generate ticket for a service
    service_id = request.data.get('service_id')
    
    if not service_id:
        return Response({'success': False,'message': 'service_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        service = Service.objects.get(id=service_id, is_active=True)
    except Service.DoesNotExist:
        return Response({'success': False,'message': 'Service not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
    
    # Create ticket
    ticket = Ticket.objects.create(service=service)
    
    # Prepare response
    response_data = {
        'success': True,
        'message': f'Ticket {ticket.display_number} generated for {service.name}',
        'ticket': {
            'ticket_id': str(ticket.ticket_id),
            'service': service.name,
            'queue_number': ticket.queue_number,
            'display_number': ticket.display_number,
            'ticket_date': str(ticket.ticket_date),
            'is_today': ticket.is_today,
            'status': ticket.status,
            'people_ahead': ticket.people_ahead,
            'wait_time_minutes': ticket.wait_time_minutes,
            'created_at': ticket.created_at.isoformat(),
        },
    }
    
    return Response(response_data, status=status.HTTP_201_CREATED)

@extend_schema(
    summary="Generate Ticket",
    description="Generate a new ticket for a specific service",
    tags=['Public Endpoints']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def ticket_status(request, ticket_id):
    # Public: Check ticket status
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        serializer = TicketSerializer(ticket)
        
        # Get queue info
        service_today = Ticket.objects.filter(
            service=ticket.service,
            ticket_date=ticket.ticket_date
        ).order_by('queue_number')
        
        current_serving = service_today.filter(status='serving').first()
        
        return Response({
            'success': True,
            'ticket': serializer.data,
            'queue_info': {
                'position': ticket.people_ahead + 1,
                'total_in_queue': service_today.filter(status__in=['waiting', 'notified']).count(),
                'currently_serving': current_serving.display_number if current_serving else None,
                'estimated_wait_minutes': ticket.wait_time_minutes
            }
        })
    except Ticket.DoesNotExist:
        return Response({'success': False,'message': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="Public Dashboard Status",
    description="Get dashboard status for display screens. Shows all currently serving tickets per service.",
    tags=['Public Endpoints']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_status(request):
    #Public: Get dashboard status for display screens (TV Monitor)
    #Shows all currently serving tickets across all windows
    services = Service.objects.filter(is_active=True).order_by('name')
    
    service_data = []
    for service in services:
        today = timezone.now().date()
        tickets_today = service.tickets.filter(ticket_date=today)
        
        # Get ALL currently serving tickets with their window info
        serving_tickets = tickets_today.filter(status='serving').select_related('assigned_window').order_by('assigned_window__window_number')
        
        # Format serving tickets with window details
        currently_serving_list = []
        for ticket in serving_tickets:
            if ticket.assigned_window:
                currently_serving_list.append({'ticket_number': ticket.display_number,'window_name': ticket.assigned_window.name,'window_number': ticket.assigned_window.window_number})
            else:
                currently_serving_list.append({'ticket_number': ticket.display_number,'window_name': 'Unknown Window','window_number': None})
        
        # Get waiting tickets
        waiting_tickets = tickets_today.filter(
            status__in=['waiting', 'notified']
        ).order_by('queue_number')
        
        # Calculate estimated wait time for next ticket
        next_wait_time = None
        if waiting_tickets.exists():
            next_wait_time = waiting_tickets.first().wait_time_minutes
        
        service_data.append({
            'id': service.id,
            'name': service.name,
            'prefix': service.prefix,
            'currently_serving': currently_serving_list, 
            'serving_count': len(currently_serving_list),
            'next_in_line': waiting_tickets.first().display_number if waiting_tickets.exists() else None,
            'waiting_count': waiting_tickets.count(),
            'estimated_next_wait': next_wait_time,
            'average_wait_time': service.average_service_time * waiting_tickets.count()
        })
    
    # Also get overall stats for the TV display
    total_waiting = sum(s['waiting_count'] for s in service_data)
    total_serving = sum(s['serving_count'] for s in service_data)
    
    return Response({
        'success': True,
        'timestamp': timezone.now().isoformat(),
        'summary': {
            'total_waiting': total_waiting,
            'total_serving': total_serving,
        },
        'services': service_data
    })