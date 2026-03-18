import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
import pytz

logger = logging.getLogger(__name__)

# Philippine Timezone
MANILA_TZ = pytz.timezone('Asia/Manila')


def check_auto_shutdown():
    """Check if it's time to auto-shutdown all services"""
    from queueing.models import Service, SystemSettings
    from queueing.websocket_utils import send_dashboard_update, send_service_status_update

    # Get current Philippine time
    utc_now = timezone.now()
    manila_now = utc_now.astimezone(MANILA_TZ)
    current_time = manila_now.time()

    # Get global settings
    settings = SystemSettings.get_settings()

    if not settings.auto_shutdown_enabled:
        return

    shutdown_time = settings.shutdown_time

    # Convert shutdown_time from string to time object if needed
    if isinstance(shutdown_time, str):
        from datetime import datetime
        shutdown_time = datetime.strptime(shutdown_time, '%H:%M:%S').time()

    # Check if current time matches shutdown time (within same minute)
    if current_time.hour == shutdown_time.hour and current_time.minute == shutdown_time.minute:
        logger.info("Shutdown time reached. Deactivating all services.")

        # Deactivate ALL active services
        deactivated_count = Service.objects.filter(is_active=True).update(is_active=False)
        logger.info(f"Deactivated {deactivated_count} services.")

        # Broadcast updates
        try:
            send_dashboard_update()
            for service in Service.objects.all():
                send_service_status_update(service.id)
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")


def start_scheduler():
    scheduler = BackgroundScheduler(timezone=MANILA_TZ)
    scheduler.add_job(
        check_auto_shutdown,
        'interval',
        minutes=1,
        id='auto_shutdown_job',
        replace_existing=True
    )

    try:
        scheduler.start()
        logger.info("Auto-shutdown scheduler started.")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")