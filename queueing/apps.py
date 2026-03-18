from django.apps import AppConfig


class QueueingConfig(AppConfig):
    name = 'queueing'

    def ready(self):
        # Start the background APScheduler cron logic 
        import sys
        
        # Prevent scheduler from running during migrations/tests
        if 'test' in sys.argv or 'makemigrations' in sys.argv or 'migrate' in sys.argv:
            return
            
        import os
        # When using Django runserver, it launches two processes. 
        # We only want the scheduler to run in the main worker process.
        if os.environ.get('RUN_MAIN', None) == 'true' or 'daphne' in sys.argv:
            from . import scheduler
            scheduler.start_scheduler()
