from .models import Ticket
from .sms_service import PhilSMSService
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def check_and_send_sms(service_id, threshold=5):
    """
    Check all waiting tickets for a service and send SMS if people_ahead <= threshold.
    Call this after any queue position change.
    """
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
        if ahead <= threshold:
            position = ahead + 1
            message = (f"Your ticket {ticket.display_number} is now #{position} in line "
                       f"at {ticket.service.name}. Please proceed to the window.")
            # Avoid using URL shorteners as per PhilSMS advisory
            success, _ = sms.send_sms(ticket.sms_phone, message)
            if success:
                ticket.sms_sent = True
                ticket.sms_sent_at = timezone.now()
                ticket.save(update_fields=['sms_sent', 'sms_sent_at'])
                logger.info(f"SMS sent for ticket {ticket.display_number}")
            else:
                logger.warning(f"Failed to send SMS for ticket {ticket.display_number}")