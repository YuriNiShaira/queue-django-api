import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone

logger = logging.getLogger(__name__)

# Keep a simple in-memory dictionary of states since LocMemCache can sometimes behave weirdly across threads
_SERVICE_STATE_CACHE = {}

def evaluate_service_schedules():
    from queueing.models import Service
    from queueing.websocket_utils import send_service_status_update

    # We only check services that have auto schedule enabled and active = True
    services = Service.objects.filter(is_active=True, auto_schedule_enabled=True)
    
    print(f"[{timezone.localtime().strftime('%H:%M:%S')}] APScheduler: Checking {services.count()} scheduled services...")
    
    for service in services:
        # Determine the current status
        current_status = service.can_accept_tickets()
        
        previous_status = _SERVICE_STATE_CACHE.get(service.id, None)

        if previous_status is None:
            # First run, initialize cache
            _SERVICE_STATE_CACHE[service.id] = current_status
            print(f"[{timezone.localtime().strftime('%H:%M:%S')}] Initialized cache for {service.name}: Accepting = {current_status}")
        elif previous_status != current_status:
            # Shift detected! 
            print(f"[{timezone.localtime().strftime('%H:%M:%S')}] 🛑 ALARM: Schedule toggle detected for {service.name} (Now: {current_status}). Broadcasting WebSocket...")
            logger.info(f"Schedule toggle detected for {service.name}: Accepting Tickets = {current_status}")
            
            # Broadcast the change via websockets
            try:
                send_service_status_update(service.id)
            except Exception as e:
                print(f"Failed to broadcast: {e}")
                logger.error(f"Failed to broadcast schedule update for {service.name}: {e}")
            
            # Update cache to latest state
            _SERVICE_STATE_CACHE[service.id] = current_status

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Run the check every minute
    scheduler.add_job(evaluate_service_schedules, 'interval', minutes=1, id='service_schedule_job', replace_existing=True)
    
    try:
        scheduler.start()
        print("✅ APScheduler Background Job Started Successfully!")
        logger.info("APScheduler started successfully.")
    except Exception as e:
        logger.error(f"Failed to start APScheduler: {e}")
