from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Ticket

#iwas talon
_last_update_time = {}
from time import time

def debounced_send_queue_updates(service_id, current_ticket_id=None, delay=0.5):
    """Prevent multiple rapid updates"""
    global _last_update_time
    
    key = f"queue_{service_id}"
    now = time()
    
    if key in _last_update_time and now - _last_update_time[key] < delay:
        print(f"Debouncing queue update for service {service_id}")
        return
    
    _last_update_time[key] = now
    send_queue_position_updates(service_id, current_ticket_id)


def send_dashboard_update():
    """Send update to all connected public dashboards"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'public_dashboard',
        {'type': 'dashboard_update'}
    )

def send_service_update(service_id):
    """Send update to all staff dashboards for a specific service"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'service_{service_id}',
        {'type': 'queue_update'}
    )

def send_ticket_update(ticket_id):
    """Send update to a specific ticket"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'ticket_{ticket_id}',
        {'type': 'ticket_update'}
    )

def send_queue_position_updates(service_id, current_ticket_id=None):
    """
    Send updates to ALL waiting tickets in a service
    But only if their position actually changed
    """
    from django.utils import timezone
    from .models import Ticket
    import logging
    
    logger = logging.getLogger(__name__)
    today = timezone.now().date()
    
    # Get all waiting tickets for this service
    waiting_tickets = Ticket.objects.filter(
        service_id=service_id,
        ticket_date=today,
        status__in=['waiting', 'notified']
    ).order_by('queue_number')
    
    # Track previous position to detect changes
    previous_position = None
    for index, ticket in enumerate(waiting_tickets):
        current_position = index + 1  # 1-based position
        
        # Only send update if position changed or it's the next ticket
        if previous_position != current_position:
            logger.info(f"Position changed for {ticket.display_number}: now #{current_position}")
            send_ticket_update(str(ticket.ticket_id))
        
        previous_position = current_position
    
    # Always update the currently serving ticket
    if current_ticket_id:
        send_ticket_update(current_ticket_id)