import uuid
from django.db import models
from django.utils import timezone
# Create your models here.

class Service(models.Model):
  SERVICES_CHOICES = [
    ('cashier', 'Cashier'),
    ('permit', 'Permit'),
    ('registrar', 'Registrar'),
  ]

  name = models.CharField(max_length=50, choices=SERVICES_CHOICES, unique=True)
  description = models.TextField(blank=True)
  windows = models.CharField(max_length=100)
  is_active = models.BooleanField(default=True)
  average_service_time = models.PositiveIntegerField(default=5)

  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  class Meta:
      ordering = ['name']
      verbose_name = 'Service'
      verbose_name_plural = 'Services'
    
  def __str__(self):
        return f"{self.get_name_display()} (Windows: {self.windows})"
    
  def get_windows_list(self):
        """Helper method to return windows as list"""
        if self.windows:
            return [w.strip() for w in self.windows.split(',')]
        return []
  
class Ticket(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('notified', 'Notified (Within 5)'),
        ('serving', 'Currently Serving'),
        ('served', 'Served'),
        ('cancelled', 'Cancelled'),
    ]
    
    ticket_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='tickets')
    queue_number = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    
    # For daily reset - store the date separately
    ticket_date = models.DateField()
    
    notified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    
    assigned_window = models.CharField(max_length=10, blank=True)
    
    class Meta:
        ordering = ['service', 'ticket_date', 'queue_number']
        unique_together = ['service', 'queue_number', 'ticket_date']
        verbose_name = 'Queue Ticket'
        verbose_name_plural = 'Queue Tickets'
    
    def __str__(self):
        return f"{self.service.get_name_display()} #{self.queue_number:03d} ({self.ticket_date})"
    
    def save(self, *args, **kwargs):
        """Auto-generate queue number with daily reset"""
        if not self.pk:
            # Set ticket date to today
            self.ticket_date = timezone.now().date()
            
            # Get the last ticket number for this service today
            last_ticket = Ticket.objects.filter(
                service=self.service,
                ticket_date=self.ticket_date
            ).order_by('-queue_number').first()
            
            # Set next queue number
            if last_ticket:
                self.queue_number = last_ticket.queue_number + 1
            else:
                self.queue_number = 1
        
        super().save(*args, **kwargs)
    
    def get_display_number(self):
        """Format: 001, 002, etc."""
        return f"{self.queue_number:03d}"
    
    @property
    def people_ahead(self):
        """Count people ahead in queue TODAY"""
        if self.status in ['serving', 'served', 'cancelled']:
            return 0
        
        return Ticket.objects.filter(
            service=self.service,
            ticket_date=self.ticket_date,
            status__in=['waiting', 'notified'],
            queue_number__lt=self.queue_number
        ).count()
    
    @property
    def is_today(self):
        """Check if ticket is from today"""
        return self.ticket_date == timezone.now().date()