from .models import Ticket, SMSSettings
from .sms_service import PhilSMSService
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def check_and_send_sms(service_id, threshold=None):
    """
    Check all queued tickets for a service and send SMS based on settings.
    
    NEW LOGIC: Send SMS when ticket is within 'threshold' positions from being served.
    
    Example with threshold=10:
    - Ticket #15 will get SMS when current serving reaches #5 (15-5=10)
    - Ticket #20 will get SMS when current serving reaches #10 (20-10=10)
    """
    from .models import Service

    try:
        service = Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        logger.warning(f"Service {service_id} not found while checking SMS")
        return

    settings = SMSSettings.get_service_settings(service)

    if not settings.sms_enabled:
        logger.info(f"SMS disabled for service {service_id}, skipping notifications")
        return

    # Use provided threshold or get from settings
    active_threshold = threshold if threshold is not None else settings.notification_threshold
    
    logger.info(f"[SMS DEBUG] Service: {service.name}, Threshold: {active_threshold}")

    sms = PhilSMSService()
    today = timezone.now().date()

    # Get current serving tickets for this service
    current_serving_tickets = Ticket.objects.filter(
        service_id=service_id,
        ticket_date=today,
        status='serving'
    ).order_by('queue_number')
    
    if not current_serving_tickets.exists():
        logger.info(f"No tickets currently being served for service {service_id}")
        return
    
    # Get the highest queue number being served (the furthest along)
    current_serving_number = current_serving_tickets.last().queue_number
    logger.info(f"[SMS DEBUG] Current serving ticket numbers: {[t.queue_number for t in current_serving_tickets]}")
    logger.info(f"[SMS DEBUG] Highest serving number: {current_serving_number}")

    # Get all waiting tickets that haven't been notified yet
    tickets = Ticket.objects.filter(
        service_id=service_id,
        ticket_date=today,
        status__in=['waiting', 'notified'],
        sms_phone__isnull=False,
        sms_sent=False
    ).select_related('service').order_by('queue_number')

    for ticket in tickets:
        # Calculate how many positions away from being served
        positions_away = ticket.queue_number - current_serving_number
        
        logger.info(
            f"[SMS DEBUG] Ticket #{ticket.queue_number} ({ticket.display_number}), "
            f"Current serving: #{current_serving_number}, "
            f"Positions away: {positions_away}, "
            f"Threshold: {active_threshold}"
        )

        # Send SMS if ticket is within threshold positions from being served
        if 0 < positions_away <= active_threshold:
            # Only send if not already sent
            if not ticket.sms_sent:
                message = (
                    f"Your ticket {ticket.display_number} is now #{positions_away} in line "
                    f"at {ticket.service.name}. Current serving: #{current_serving_number}. "
                    f"Please prepare to proceed to the window."
                )

                success, response = sms.send_sms(ticket.sms_phone, message)

                if success:
                    ticket.sms_sent = True
                    ticket.sms_sent_at = timezone.now()
                    ticket.save(update_fields=['sms_sent', 'sms_sent_at'])

                    logger.info(
                        f"SMS sent for ticket {ticket.display_number} "
                        f"(positions away: {positions_away})"
                    )
                else:
                    logger.warning(
                        f"Failed to send SMS for ticket {ticket.display_number}. "
                        f"Response: {response}"
                    )
        elif positions_away <= 0:
            logger.info(f"Ticket {ticket.display_number} has already been served or passed")