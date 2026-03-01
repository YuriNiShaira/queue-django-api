from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import Ticket, ServiceWindow
from .serializers import TicketSerializer, ServiceWindowSerializer
from .permissions import IsServiceStaff
from drf_spectacular.utils import extend_schema


@extend_schema(
    summary="queue management",
    description="Staff operations for managing queues",
    tags=['Staff Queue Management']
)
@api_view(['GET'])
@permission_classes([IsServiceStaff])
def staff_dashboard(request):
    # Dashboard showing queue and per-window status
    if not hasattr(request.user, 'staff_profile'):
        return Response({'success': False, 'message': 'Not staff'}, status=403)
    
    staff_profile = request.user.staff_profile
    service = staff_profile.assigned_service
    
    if not service:
        return Response({'success': False, 'message': 'No service assigned'}, status=400)
    
    today = timezone.now().date()
    
    # Get queue
    waiting = Ticket.objects.filter(
        service=service,
        ticket_date=today,
        status='waiting'
    ).order_by('queue_number')
    
    windows_status = []
    for window in service.windows.filter(status='active'):
        serving = Ticket.objects.filter(
            service=service,
            assigned_window=window,
            ticket_date=today,
            status='serving'
        ).first()
        
        windows_status.append({
            'id': window.id,
            'name': window.name,
            'number': window.window_number,
            'currently_serving': {
                'ticket_id': serving.ticket_id,
                'display_number': serving.display_number
            } if serving else None,
            'is_available': True
        })
    
    return Response({
        'success': True,
        'dashboard': {
            'service': service.name,
            'waiting_count': waiting.count(),
            'next_ticket': waiting.first().display_number if waiting.exists() else None,
            'waiting_list': TicketSerializer(waiting[:10], many=True).data,
            'windows': windows_status
        }
    })


@extend_schema(
    summary="Call Next Ticket",
    description="Call the next waiting ticket to a specific window. Auto-completes any ticket currently at that window.",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def call_next_ticket(request):
    #Call the next waiting ticket

    # Check if user has staff profile
    if not hasattr(request.user, 'staff_profile'):
        return Response({'success': False,'message': 'User is not a staff member'}, status=status.HTTP_403_FORBIDDEN)
    
    staff_profile = request.user.staff_profile
    service = staff_profile.assigned_service
    
    if not service:
        return Response({'success': False,'message': 'No service assigned'}, status=400)
    
    window_id = request.data.get('window_id')
    if not window_id:
        return Response({'success': False,'message': 'window_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        window = ServiceWindow.objects.get(id=window_id, service=service, status='active')
    except ServiceWindow.DoesNotExist:
        return Response({'success': False, 'message': 'Window not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
        
    
    today = timezone.now().date()
    
    from django.db import transaction
    # STEP 1: Check if this window is already serving a ticket
    with transaction.atomic():
        current_serving = Ticket.objects.filter(
            service=service,
            assigned_window=window,
            ticket_date=today,
            status='serving'
        ).select_for_update().first()

        if current_serving:
            current_serving.status = 'served'
            current_serving.served_by = request.user
            current_serving.served_at = timezone.now()
            current_serving.save()
            completed_ticket = current_serving.display_number
        else:
            completed_ticket = None

        # STEP 2: Find next waiting ticket
        next_ticket = Ticket.objects.filter(
            service=service,
            ticket_date=today,
            status='waiting'
        ).select_for_update().order_by('queue_number').first()

        if not next_ticket:
            message = 'No tickets waiting in queue'
            if completed_ticket:
                message = f'Ticket {completed_ticket} completed at {window.name}. No more tickets waiting.'

            return Response({'success': False, 'message': message}, status=status.HTTP_404_NOT_FOUND)
        
        # STEP 3: Assign next ticket to this window
        next_ticket.status = 'serving'
        next_ticket.called_by = request.user
        next_ticket.called_at = timezone.now()
        next_ticket.assigned_window = window  # Assign to specific window
        next_ticket.save()

        # STEP 4: Get queue info for response
        waiting_count = Ticket.objects.filter(service=service, ticket_date=today, status='waiting').count()

        next_waiting = Ticket.objects.filter(service=service, ticket_date=today, status='waiting').order_by('queue_number').first()

    if completed_ticket:
        message = f'{window.name}: Ticket {completed_ticket} completed. Now serving {next_ticket.display_number}'
    else:
        message = f'{window.name}: Now serving {next_ticket.display_number}'

    return Response({
        'success': True,
        'message': message,
        'ticket': {
            'ticket_id': next_ticket.ticket_id,
            'display_number': next_ticket.display_number,
            'queue_number': next_ticket.queue_number,
            'status': next_ticket.status,
            'people_ahead': next_ticket.people_ahead,
            'window': {
                'id': window.id,
                'name': window.name,
                'number': window.window_number
            }
        },
        'completed_ticket': completed_ticket,
        'window': {
            'id': window.id,
            'name': window.name,
            'number': window.window_number
        },
        'queue_info': {
            'waiting_count': waiting_count,
            'next_waiting': next_waiting.display_number if next_waiting else None
        }
    })




@extend_schema(
    summary="Call Specific Ticket",
    description="Call a specific ticket by its display number (e.g., 'C001')",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def call_specific_ticket(request):
    #Call a specific ticket by number
    ticket_number = request.data.get('ticket_number')
    window_id = request.data.get('window_id')
    
    if not ticket_number:
        return Response({'success': False,'message': 'ticket_number is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not window_id:
        return Response({'success': False, 'message': 'window_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    staff_profile = request.user.staff_profile
    service = staff_profile.assigned_service
    
    try:
        window = ServiceWindow.objects.get(
            id=window_id,
            service=service,
            status='active'
        )
    except ServiceWindow.DoesNotExist:
        return Response({'success': False, 'message': 'Window not found or inactive'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    
    from django.db import transaction

    with transaction.atomic():
        try:
            ticket = Ticket.objects.select_for_update().get(
                service = service,
                ticket_date = today,
                display_number = ticket_number
            )
        except Ticket.DoesNotExist:
            return Response({'success': False,'message': f'Ticket {ticket_number} not found in today\'s queue'}, status=status.HTTP_404_NOT_FOUND)
        
        if ticket.status not in ['waiting', 'notified']:
            return Response({'success': False, 'message': f'Ticket {ticket_number} cannot be called (current status: {ticket.status})'}, status=status.HTTP_400_BAD_REQUEST)

        current_serving = Ticket.objects.filter(
            service=service,
            assigned_window=window,
            ticket_date=today,
            status='serving'
        ).select_for_update().first()

        if current_serving:
            current_serving.status = 'served'
            current_serving.served_by = request.user
            current_serving.served_at = timezone.now()
            current_serving.save()
            completed_ticket = current_serving.display_number
        else:
            completed_ticket = None

        ticket.status = 'serving'
        ticket.called_by = request.user
        ticket.called_at = timezone.now()
        ticket.assigned_window = window
        ticket.save()

    return Response({
        'success': True,
        'message': f'Ticket {ticket.display_number} called to {window.name}',
        'ticket': {
            'ticket_id': ticket.ticket_id,
            'display_number': ticket.display_number,
            'status': ticket.status,
            'window': {
                'id': window.id,
                'name': window.name,
                'number': window.window_number
            }
        },
        'completed_ticket': completed_ticket
    })


@extend_schema(
    summary="Start Serving",
    description="Start serving a ticket (can be from waiting or notified status)",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def start_serving(request, ticket_id):
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        if ticket.service != request.user.staff_profile.assigned_service:
            return Response({'success': False,'message': 'You do not have permission to serve tickets from this service'}, status=status.HTTP_403_FORBIDDEN)
        
        if ticket.status not in ['waiting', 'notified']:
            return Response({'success': False,'message': f'Ticket must be in "waiting" or "notified" status. Current: {ticket.status}'}, status=status.HTTP_400_BAD_REQUEST)
        
        window_id = request.data.get('window_id')
        if not window_id:
            return Response({'success': False,'message': 'window_id is required'}, status=400)

        try:
            window = ServiceWindow.objects.get(
                id=window_id,
                service=ticket.service,
                status='active'
            )
        except ServiceWindow.DoesNotExist:
            return Response({'success': False,'message': 'Window not found or inactive'}, status=404)

        ticket.status = 'serving'
        ticket.assigned_window = window
        ticket.save()

        return Response({'success': True,'message': f'Now serving ticket {ticket.display_number} at {window.name}','ticket': TicketSerializer(ticket).data})
        
    except Ticket.DoesNotExist:
        return Response({'success': False,'message': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="Complete Serving",
    description="Manually mark a ticket as served",
    tags=['Staff Queue Management']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def complete_serving(request, ticket_id):
    #manual served
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        if ticket.service != request.user.staff_profile.assigned_service:
            return Response({'success': False, 'message': 'You do not have permission to serve tickets from this service'}, status=status.HTTP_403_FORBIDDEN)
        
        if ticket.status != 'serving':
            return Response({'success': False,'message': f'Ticket must be in "serving" status. Current: {ticket.status}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update ticket
        ticket.status = 'served'
        ticket.served_by = request.user
        ticket.served_at = timezone.now()
        ticket.save()
        
        return Response({
            'success': True,
            'message': f'Ticket {ticket.display_number} marked as served',
            'ticket': {
                'ticket_id': ticket.ticket_id,
                'display_number': ticket.display_number,
                'status': ticket.status
            }
        })
        
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