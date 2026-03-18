from django.apps import AppConfig
import sys
import os

class QueueingConfig(AppConfig):
    name = 'queueing'

    def ready(self):
        # Skip during management commands
        if any(arg in sys.argv for arg in ['test', 'makemigrations', 'migrate']):
            return
        
        # Start scheduler for Daphne or main runserver process
        if 'daphne' in sys.argv[0] or os.environ.get('RUN_MAIN') == 'true':
            try:
                from . import scheduler
                scheduler.start_scheduler()
            except Exception as e:
                print(f"❌ Failed to start scheduler: {e}")