from .models import Ticket, SMSSettings
from .sms_service import PhilSMSService
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def check_and_send_sms(service_id, threshold=None):
    """
    Check all waiting tickets for a service and send SMS based on settings.
    If threshold is provided, it overrides the saved setting.
    """
    # Get settings for this service
    from .models import Service
    service = Service.objects.get(id=service_id)
    settings = SMSSettings.get_service_settings(service)
    
    # Check if SMS is globally enabled
    if not settings.sms_enabled:
        logger.info(f"SMS disabled globally, skipping notifications for service {service_id}")
        return
    
    # Use provided threshold or get from settings
    active_threshold = threshold if threshold is not None else settings.notification_threshold
    
    sms = PhilSMSService()
    today = timezone.now().date()

    tickets = Ticket.objects.filter(
        service_id=service_id,
        ticket_date=today,
        status='waiting',
        sms_phone__isnull=False,
        sms_sent=False
    ).select_related('service')

    for ticket in tickets:
        ahead = ticket.people_ahead
        if ahead <= active_threshold:
            position = ahead + 1
            message = (f"Your ticket {ticket.display_number} is now #{position} in line "
                       f"at {ticket.service.name}. Please proceed to the window.")
            
            success, _ = sms.send_sms(ticket.sms_phone, message)
            if success:
                ticket.sms_sent = True
                ticket.sms_sent_at = timezone.now()
                ticket.save(update_fields=['sms_sent', 'sms_sent_at'])
                logger.info(f"SMS sent for ticket {ticket.display_number} (threshold: {active_threshold})")
            else:
                logger.warning(f"Failed to send SMS for ticket {ticket.display_number}")