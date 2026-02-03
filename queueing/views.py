from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import Window, Ticket
from .serializers import WindowSerializer, TicketSerializer
from .escpos_utils import MockPrinter
from django.utils import timezone

@api_view(['GET'])
@permission_classes([AllowAny])
def window_list(request):
    """Get all windows"""
    service_type = request.query_params.get('service_type')
    active_only = request.query_params.get('active_only', 'true').lower() == 'true'
    
    queryset = Window.objects.all()
    
    if active_only:
        queryset = queryset.filter(status='active')
    
    if service_type:
        queryset = queryset.filter(service_type=service_type)
    
    queryset = queryset.order_by('number')
    serializer = WindowSerializer(queryset, many=True)
    
    return Response({
        'success': True,
        'count': queryset.count(),
        'windows': serializer.data
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_ticket(request):
    window_id = request.data.get('window_id')
    service_group = request.data.get('service_group')

    # Validate input
    if not window_id and not service_group:
        return Response({
            'success': False,
            'message': 'Either window_id (for registrar/permit) or service_group (for cashier) is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        if window_id:
            # Registrar or Permit ticket
            window = Window.objects.get(id=window_id, status='active')

            # Check if window is for registrar or permit
            if window.service_type not in ['registrar', 'permit']:
                 return Response({
                    'success': False,
                    'message': f'Window {window.number} is for {window.get_service_type_display()}. '
                             f'Use service_group="cashier" for cashier tickets.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create window-specific ticket
            ticket = Ticket.objects.create(window=window)
            service_name = f"{window.get_service_type_display()} - Window {window.number}"

        else:
            # Cashier ticket (shared queue)
            if service_group != 'cashier':
                return Response({
                    'success': False,
                    'message': 'For cashier tickets, use service_group="cashier"'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create cashier ticket (no specific window)
            ticket = Ticket.objects.create(service_group='cashier')
            service_name = 'Cashier'

        #generate ticket
        print_result = MockPrinter.print_ticket(ticket, save_to_file=True)

        response_data = {
            'success': True,
            'message': f'Ticket {ticket.get_display_number()} generated for {service_name}',
            'ticket': {
                'ticket_id': str(ticket.ticket_id),
                'service': service_name,
                'queue_number': ticket.queue_number,
                'display_number': ticket.get_display_number(),
                'ticket_date': str(ticket.ticket_date),
                'is_today': ticket.is_today,
                'status': ticket.status,
                'people_ahead': ticket.people_ahead,
                'created_at': ticket.created_at.isoformat(),
            },
            'printer_data': {
                'success': print_result.get('success', True),
                'preview_html': print_result.get('preview_html', ''),
            }
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    except Window.DoesNotExist:
        return Response({
            'success':False,
            'message': 'Window not found or inactive'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def ticket_status(request, ticket_id):
    try:
        ticket = Ticket.objects.get(ticket_id = ticket_id)
        serializer = TicketSerializer(ticket)

        # Get currently serving ticket
        if ticket.window:
            # Window-specific queue (registrar/permit)
            current_serving = Ticket.objects.filter(
                window=ticket.window,
                ticket_date=ticket.ticket_date,
                status='serving'
            ).first()
        else:
            # Service group queue (cashier)
            current_serving = Ticket.objects.filter(
                service_group = ticket.service_group,
                ticket_date = ticket.ticket_date,
                status='serving'
            ).first()

        return Response({
            'success': True,
            'ticket': serializer.data,
            'queue_info': {
                'position': ticket.people_ahead + 1,
                'currently_serving': current_serving.display_number if current_serving else None,
                'estimated_wait_minutes': ticket.people_ahead * 5  # 5 minutes average
            }
        })
    except Ticket.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Ticket not found'
        }, status=status.HTTP_404_NOT_FOUND)
    


@api_view(['GET'])
@permission_classes([AllowAny])
def service_status(request):
    #Get current status of all services
    # Get all active windows grouped by service
    windows = Window.objects.filter(status='active').order_by('number')
    
    service_data = {}
    
    for window in windows:
        service_type = window.service_type
        if service_type == 'other':
            continue
            
        if service_type not in service_data:
            service_data[service_type] = {
                'name': window.get_service_type_display(),
                'windows': [],
                'total_waiting': 0,
                'currently_serving': None
            }
        
        # Get tickets for this widow today
        today = timezone.now().date()
        waiting_count = Ticket.objects.filter(
            window=window,
            ticket_date=today,
            status__in=['waiting', 'notified']
        ).count()
        
        currently_serving = Ticket.objects.filter(
            window=window,
            ticket_date=today,
            status='serving'
        ).first()
        
        service_data[service_type]['windows'].append({
            'number': window.number,
            'name': window.name,
            'waiting_count': waiting_count,
            'currently_serving': currently_serving.display_number if currently_serving else None
        })
        
        service_data[service_type]['total_waiting'] += waiting_count
    
    # Add cashier service 
    cashier_windows = windows.filter(service_type='cashier')
    if cashier_windows.exists():
        today = timezone.now().date()
        cashier_waiting = Ticket.objects.filter(
            service_group='cashier',
            ticket_date=today,
            status__in=['waiting', 'notified']
        ).count()
        
        cashier_serving = Ticket.objects.filter(
            service_group='cashier',
            ticket_date=today,
            status='serving'
        ).first()
        
        service_data['cashier'] = {
            'name': 'Cashier',
            'windows': [
                {
                    'number': w.number,
                    'name': w.name,
                    'waiting_count': 0,  # Shared queue, don't count per window
                    'currently_serving': None
                } for w in cashier_windows
            ],
            'total_waiting': cashier_waiting,
            'currently_serving': cashier_serving.display_number if cashier_serving else None
        }
    
    return Response({
        'success': True,
        'services': service_data,
        'timestamp': timezone.now().isoformat()
    })
    
    


    

    

