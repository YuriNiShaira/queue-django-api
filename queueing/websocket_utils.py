from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Ticket
from django.utils import timezone
from time import time

_last_update_time = {}

def send_ticket_update(ticket_id):
    """Send update to a specific ticket"""
    ticket_id_str = str(ticket_id)
    group_name = f'ticket_{ticket_id_str}'

    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'ticket_update',
                'ticket_id': ticket_id_str
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    return True

def send_dashboard_update():
    """Send update to public dashboard"""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    
    try:
        async_to_sync(channel_layer.group_send)(
            'public_dashboard',
            {'type': 'dashboard_update'}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()

def send_service_update(service_id):
    """Send update to all staff dashboards for a specific service"""
    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            f'service_{service_id}',
            {'type': 'queue_update'}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()

def send_queue_position_updates(service_id, current_ticket_id=None):
    """Send updates to all waiting tickets in a service"""
    today = timezone.now().date()
    waiting_tickets = Ticket.objects.filter(
        service_id=service_id,
        ticket_date=today,
        status__in=['waiting', 'notified']
    )

    for ticket in waiting_tickets:
        send_ticket_update(str(ticket.ticket_id))

    if current_ticket_id:
        send_ticket_update(current_ticket_id)

def debounced_send_queue_updates(service_id, current_ticket_id=None, delay=0.5):
    """Prevent multiple rapid updates"""
    global _last_update_time
    key = f"queue_{service_id}"
    now = time()

    if key in _last_update_time and now - _last_update_time[key] < delay:
        return

    _last_update_time[key] = now
    send_queue_position_updates(service_id, current_ticket_id)


def send_service_status_update(service_id, is_active=None):
    """Send service status update to all subscribers"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'service_status_{service_id}',
        {
            'type': 'service_status_update',
            'service_id': service_id,
            'is_active': is_active
        }
    )
    
    # Also update dashboards
    send_dashboard_update()
    send_service_update(service_id)


