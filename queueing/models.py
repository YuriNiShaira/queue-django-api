import uuid
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_migrate
from django.dispatch import receiver

class Window(models.Model):
    WINDOW_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
    ]
    
    number = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    service_type = models.CharField(max_length=50, choices=[
        ('cashier', 'Cashier'),
        ('permit', 'Permit'),
        ('registrar', 'Registrar'),
        ('other', 'Other'),
    ], default='other')
    status = models.CharField(max_length=20, choices=WINDOW_STATUS, default='active')
    description = models.TextField(blank=True)
    
    # Queue management for this window
    current_queue_number = models.PositiveIntegerField(default=0)
    last_queue_reset = models.DateField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Window {self.number}: {self.name or self.get_service_type_display()}"
    
    class Meta:
        ordering = ['number']
    
    def get_next_queue_number(self):
        """Get the next queue number for this window, resetting if new day"""
        today = timezone.now().date()
        
        if self.last_queue_reset != today:
            self.current_queue_number = 0
            self.last_queue_reset = today
            self.save()
        
        self.current_queue_number += 1
        self.save()
        return self.current_queue_number

class Service(models.Model):
    SERVICES_CHOICES = [
        ('cashier', 'Cashier'),
        ('permit', 'Permit'),
        ('registrar', 'Registrar'),
    ]
    
    name = models.CharField(max_length=50, choices=SERVICES_CHOICES, unique=True)
    description = models.TextField(blank=True)
    windows = models.ManyToManyField(Window, related_name='services', blank=True)
    is_active = models.BooleanField(default=True)
    average_service_time = models.PositiveIntegerField(default=5)
    
    # For daily queue reset
    current_queue_number = models.PositiveIntegerField(default=0)
    last_queue_reset = models.DateField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.get_name_display()}"
    
    def get_windows_list(self):
        """Return list of window numbers assigned to this service"""
        return list(self.windows.filter(status='active').values_list('number', flat=True))
    
    def get_next_queue_number(self):
        """Get the next queue number, resetting if it's a new day"""
        today = timezone.now().date()
        
        if self.last_queue_reset != today:
            self.current_queue_number = 0
            self.last_queue_reset = today
            self.save()
        
        self.current_queue_number += 1
        self.save()
        return self.current_queue_number

class Ticket(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('notified', 'Notified'),
        ('serving', 'Currently Serving'),
        ('served', 'Served'),
        ('cancelled', 'Cancelled'),
    ]
    
    ticket_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Ticket belongs to a specific window (for registrar)
    # OR to a service group (for cashier - shared queue)
    window = models.ForeignKey(
        Window, 
        on_delete=models.CASCADE, 
        related_name='tickets',
        null=True,
        blank=True,
        help_text="Specific window for registrar/permit"
    )
    
    # For cashier (shared queue among windows 6,7,8,9)
    service_group = models.CharField(max_length=50, choices=[
        ('cashier', 'Cashier'),
        ('permit', 'Permit'),
        ('registrar', 'Registrar'),
    ], null=True, blank=True)
    
    queue_number = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    
    # For daily reset
    ticket_date = models.DateField()
    notified = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    
    # For cashier tickets - which window actually served it
    served_window = models.ForeignKey(
        Window,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='served_tickets'
    )
    
    class Meta:
        ordering = ['ticket_date', 'queue_number']
        unique_together = [
            ['window', 'queue_number', 'ticket_date'],  # For registrar/permit
            ['service_group', 'queue_number', 'ticket_date'],  # For cashier
        ]
    
    def __str__(self):
        if self.window:
            return f"Window {self.window.number} #{self.queue_number:03d}"
        else:
            return f"{self.get_service_group_display()} #{self.queue_number:03d}"
    
    def save(self, *args, **kwargs):
        """Auto-generate queue number with daily reset"""
        if not self.pk:
            self.ticket_date = timezone.now().date()
            
            # Determine which queue to use
            if self.window:  # Registrar or Permit (window-specific queue)
                self.queue_number = self.window.get_next_queue_number()
                self.service_group = self.window.service_type
            else:  # Cashier (shared queue)
                # Find the last cashier ticket today
                last_ticket = Ticket.objects.filter(
                    service_group='cashier',
                    ticket_date=self.ticket_date
                ).order_by('-queue_number').first()
                
                if last_ticket:
                    self.queue_number = last_ticket.queue_number + 1
                else:
                    self.queue_number = 1
            
            # Set service group for cashier
            if not self.service_group and self.window:
                self.service_group = self.window.service_type
        
        super().save(*args, **kwargs)
    
    def get_display_number(self):
        """Format: 001, 002, etc."""
        return f"{self.queue_number:03d}"
    
    @property
    def display_service(self):
        """Get display name of service/window"""
        if self.window:
            return f"{self.window.get_service_type_display()} - Window {self.window.number}"
        else:
            return self.get_service_group_display()
    
    @property
    def people_ahead(self):
        """Count people ahead in queue TODAY"""
        if self.status in ['serving', 'served', 'cancelled']:
            return 0
        
        if self.window:  # Window-specific queue
            return Ticket.objects.filter(
                window=self.window,
                ticket_date=self.ticket_date,
                status__in=['waiting', 'notified'],
                queue_number__lt=self.queue_number
            ).count()
        else:  # Service group queue (cashier)
            return Ticket.objects.filter(
                service_group=self.service_group,
                ticket_date=self.ticket_date,
                status__in=['waiting', 'notified'],
                queue_number__lt=self.queue_number
            ).count()
    
    @property
    def is_today(self):
        """Check if ticket is from today"""
        return self.ticket_date == timezone.now().date()
    
    @property
    def service_name(self):
        if self.window:
            return f"{self.window.get_service_type_display()} - Window {self.window.number}"
        return self.get_service_group_display()

# Signal to create windows based on your school setup
@receiver(post_migrate)
def create_initial_windows(sender, **kwargs):
    if sender.name == 'queueing':
        if not Window.objects.exists():
            windows_data = [
                # (window_number, name, service_type, status)
                (1, 'Not in use', 'other', 'inactive'),
                (2, 'Registrar 1', 'registrar', 'active'),
                (3, 'Registrar 2', 'registrar', 'active'),
                (4, 'Not in use', 'other', 'inactive'),
                (5, 'Permit Office', 'permit', 'active'),
                (6, 'Cashier 1', 'cashier', 'active'),
                (7, 'Cashier 2', 'cashier', 'active'),
                (8, 'Cashier 3', 'cashier', 'active'),
                (9, 'Cashier 4', 'cashier', 'active'),
                (10, 'Not in use', 'other', 'inactive'),
            ]
            
            for number, name, service_type, status in windows_data:
                Window.objects.create(
                    number=number,
                    name=name,
                    service_type=service_type,
                    status=status
                )
            
            print("✓ Created 10 windows with correct service types")
