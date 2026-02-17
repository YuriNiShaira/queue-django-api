# queueing/staff_dashboard_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import Service, Ticket
from .serializers import TicketSerializer, ServiceSerializer
from .permissions import IsServiceStaff, HasServicePermission
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes


@extend_schema(
    summary="queue management",
    description="Staff operations for managing queues",
    tags=['Staff Queue Management']
)
@api_view(['GET'])
@permission_classes([IsServiceStaff])
def staff_dashboard(request):
    #Get staff dashboard for assigned service
    staff_profile = request.user.staff_profile
    service = staff_profile.assigned_service
    
    if not service:
        return Response({'success': False,'message': 'No service assigned to your account'}, status=status.HTTP_400_BAD_REQUEST)
    
    today = timezone.now().date()
    
    # Get queue data
    tickets_today = service.tickets.filter(ticket_date=today).order_by('queue_number')
    
    # Get tickets by status
    waiting = tickets_today.filter(status='waiting')
    notified = tickets_today.filter(status='notified')
    serving = tickets_today.filter(status='serving')
    served_recent = tickets_today.filter(status='served').order_by('-served_at')[:10]
    
    # Get service windows
    windows = service.windows.filter(status='active')
    
    # Get currently serving per window
    window_status = []
    for window in windows:
        window_ticket = serving.filter(assigned_window=window).first()
        window_status.append({'window_id': window.id,'window_name': window.name or f"Window {window.window_number}",'current_ticket': TicketSerializer(window_ticket).data if window_ticket else None})
    
    return Response({
        'success': True,
        'dashboard': {
            'service': ServiceSerializer(service).data,
            'queue_stats': {
                'waiting': waiting.count(),
                'notified': notified.count(),
                'serving': serving.count(),
                'total_today': tickets_today.count(),
                'next_ticket': waiting.first().display_number if waiting.exists() else None,
            },
            'current_queue': {
                'waiting': TicketSerializer(waiting[:10], many=True).data,  # Next 10
                'notified': TicketSerializer(notified, many=True).data,
                'serving': TicketSerializer(serving, many=True).data,
            },
            'recent_served': TicketSerializer(served_recent, many=True).data,
            'windows': window_status,
        }
    })


@extend_schema(
    summary="Call Next Ticket",
    description="Call the next waiting ticket to the staff's current window",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def call_next_ticket(request):
    """Call the next waiting ticket"""
    if not hasattr(request.user, 'staff_profile'):
        return Response({'success': False,'message': 'User is not a staff member'}, status=status.HTTP_403_FORBIDDEN)
    
    staff_profile = request.user.staff_profile

     # Check if staff has selected a window
    if not staff_profile.current_window:
        return Response({'success': False,'message': 'Please select a window first'}, status=status.HTTP_400_BAD_REQUEST)
    
    service = staff_profile.assigned_service
    window = staff_profile.current_window

    # Double-check window is active
    if window.status != 'active':
        return Response({'success': False,'message': f'Window {window.name} is not active'}, status=status.HTTP_400_BAD_REQUEST)
    
    today = timezone.now().date()

    # Find next waiting ticket (priority: waiting -> notified)
    # We check 'notified' first in case someone was called but not served

    next_ticket = Ticket.objects.filter(
        service=service,
        ticket_date=today,
        status__in=['waiting', 'notified'] 
    ).order_by('queue_number').first()

    if not next_ticket:
        return Response({
            'success': False,
            'message': 'No tickets waiting in queue'
        }, status=status.HTTP_404_NOT_FOUND)
    
    #Use transaction to ensure data consistency
    from django.db import transaction

    with transaction.atomic():
        # If there's already a ticket being served at this window, complete it first
        current_serving = Ticket.objects.filter(
            assigned_window=window,
            status='serving'
        ).first()
        
        if current_serving:
            current_serving.status = 'served'
            current_serving.served_by = request.user
            current_serving.served_at = timezone.now()
            current_serving.save()
        
        # Update the new ticket
        next_ticket.status = 'serving'  # Direct to serving, skip notified if you want
        next_ticket.called_by = request.user
        next_ticket.called_at = timezone.now()
        next_ticket.assigned_window = window
        next_ticket.save()
    
    # Prepare response with queue information
    waiting_count = Ticket.objects.filter(
        service=service,
        ticket_date=today,
        status='waiting'
    ).count()
    
    return Response({
        'success': True,
        'message': f'Now serving {next_ticket.display_number} at {window.name}',
        'ticket': {
            'ticket_id': next_ticket.ticket_id,
            'display_number': next_ticket.display_number,
            'queue_number': next_ticket.queue_number,
            'status': next_ticket.status,
            'people_ahead': next_ticket.people_ahead
        },
        'window': {
            'id': window.id,
            'name': window.name,
            'number': window.window_number
        },
        'queue_info': {
            'waiting_count': waiting_count,
            'next_waiting': Ticket.objects.filter(
                service=service, 
                ticket_date=today, 
                status='waiting'
            ).order_by('queue_number').first().display_number if waiting_count > 0 else None
        }
    })


@extend_schema(
    summary="queue management",
    description="Staff operations for managing queues",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def call_specific_ticket(request):
    #Call a specific ticket by number
    ticket_number = request.data.get('ticket_number')
    
    if not ticket_number:
        return Response({'success': False,'message': 'ticket_number is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    staff_profile = request.user.staff_profile
    service = staff_profile.assigned_service
    
    today = timezone.now().date()
    
    # Find ticket by display number
    try:
        ticket = Ticket.objects.get(
            service=service,
            ticket_date=today,
            display_number=ticket_number
        )
    except Ticket.DoesNotExist:
        return Response({'success': False,'message': f'Ticket {ticket_number} not found in today\'s queue'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check ticket status
    if ticket.status != 'waiting':
        return Response({'success': False,'message': f'Ticket {ticket_number} is not waiting (status: {ticket.status})'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Update ticket
    ticket.status = 'notified'
    ticket.called_by = request.user
    ticket.called_at = timezone.now()
    ticket.save()
    
    return Response({'success': True,'message': f'Ticket {ticket.display_number} called','ticket': TicketSerializer(ticket).data})


@extend_schema(
    summary="queue management",
    description="Staff operations for managing queues",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def start_serving(request, ticket_id):
    #Start serving a called ticket
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Check permission
        if ticket.service != request.user.staff_profile.assigned_service:
            return Response({'success': False,'message': 'You do not have permission to serve tickets from this service'}, status=status.HTTP_403_FORBIDDEN)
        
        if ticket.status != 'notified':
            return Response({'success': False,'message': f'Ticket must be in "notified" status. Current: {ticket.status}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update ticket
        ticket.status = 'serving'
        ticket.save()
        
        return Response({'success': True,'message': f'Now serving ticket {ticket.display_number}','ticket': TicketSerializer(ticket).data})
        
    except Ticket.DoesNotExist:
        return Response({'success': False,'message': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="queue management",
    description="Staff operations for managing queues",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def complete_serving(request, ticket_id):
    #Mark ticket as served/completed
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Check permission
        if ticket.service != request.user.staff_profile.assigned_service:
            return Response({'success': False,'message': 'You do not have permission to serve tickets from this service'}, status=status.HTTP_403_FORBIDDEN)
        
        if ticket.status != 'serving':
            return Response({'success': False,'message': f'Ticket must be in "serving" status. Current: {ticket.status}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update ticket
        ticket.status = 'served'
        ticket.served_by = request.user
        ticket.served_at = timezone.now()
        ticket.save()
        
        return Response({'success': True,'message': f'Ticket {ticket.display_number} marked as served','ticket': TicketSerializer(ticket).data})
        
    except Ticket.DoesNotExist:
        return Response({'success': False,'message': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="queue management",
    description="Staff operations for managing queues",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def remove_ticket(request, ticket_id):
    #Remove a ticket from queue (skip or cancel)
    reason = request.data.get('reason', 'No reason provided')
    
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Check permission
        if ticket.service != request.user.staff_profile.assigned_service:
            return Response({'success': False,'message': 'You do not have permission to remove tickets from this service'}, status=status.HTTP_403_FORBIDDEN)
        
        # Can't remove served tickets
        if ticket.status == 'served':
            return Response({'success': False,'message': 'Cannot remove a served ticket'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Remove ticket (mark as cancelled)
        ticket.status = 'cancelled'
        ticket.notes = f"Removed from queue: {reason}"
        ticket.save()
        
        return Response({'success': True,'message': f'Ticket {ticket.display_number} removed from queue','ticket': TicketSerializer(ticket).data})
        
    except Ticket.DoesNotExist:
        return Response({'success': False,'message': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="queue management",
    description="Staff operations for managing queues",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def recall_ticket(request, ticket_id):
    #Recall a skipped or previously called ticket
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Check permission
        if ticket.service != request.user.staff_profile.assigned_service:
            return Response({'success': False,'message': 'You do not have permission to recall tickets from this service'}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if ticket can be recalled
        if ticket.status not in ['notified', 'skipped', 'cancelled']:
            return Response({'success': False,'message': f'Cannot recall ticket in {ticket.status} status'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Move back to waiting
        old_status = ticket.status
        ticket.status = 'waiting'
        ticket.notes = f"Recalled from {old_status}: {ticket.notes}"
        ticket.called_by = None
        ticket.called_at = None
        ticket.save()
        
        return Response({'success': True,'message': f'Ticket {ticket.display_number} recalled to waiting queue','ticket': TicketSerializer(ticket).data})
        
    except Ticket.DoesNotExist:
        return Response({'success': False,'message': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="queue management",
    description="Staff operations for managing queues",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def toggle_queue_status(request):
    #Pause or resume the queue for a service
    staff_profile = request.user.staff_profile
    service = staff_profile.assigned_service
    
    if not service:
        return Response({'success': False,'message': 'No service assigned to your account'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Toggle service active status
    service.is_active = not service.is_active
    service.save()
    
    status_text = "paused" if not service.is_active else "resumed"
    
    return Response({
        'success': True,
        'message': f'Queue for {service.name} {status_text}',
        'service': {
            'id': service.id,
            'name': service.name,
            'is_active': service.is_active
        }
    })