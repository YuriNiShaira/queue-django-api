import uuid
from django.db import models
from django.utils import timezone
from django.db.models import Max
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User


# =======================
# SERVICE MODELS
# =======================
class Service(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    prefix = models.CharField(max_length=10, default="", blank=True, unique=True)
    is_active = models.BooleanField(default=True)
    average_service_time = models.PositiveIntegerField(default=5)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_next_queue_number(self):
        today = timezone.now().date()

        last_ticket = self.tickets.filter(
            ticket_date=today
        ).aggregate(Max('queue_number'))['queue_number__max']

        if last_ticket:
            return last_ticket + 1
        return 1

    def get_display_number(self, queue_number):
        if self.prefix:
            return f"{self.prefix}{queue_number:03d}"
        return f"{queue_number:03d}"

    @property
    def waiting_count(self):
        today = timezone.now().date()
        return self.tickets.filter(
            ticket_date=today,
            status__in=['waiting', 'notified']
        ).count()

    @property
    def currently_serving(self):
        today = timezone.now().date()
        return self.tickets.filter(
            ticket_date=today,
            status='serving'
        ).first()


class ServiceWindow(models.Model):
    WINDOW_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
    ]

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='windows')
    window_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=WINDOW_STATUS, default='active')
    description = models.TextField(blank=True)

    current_staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_window')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['service', 'window_number']
        unique_together = ['service', 'window_number']

    def __str__(self):
        return f"{self.service.name} - {self.name or f'Window {self.window_number}'}"

    @property
    def is_available(self):
        return self.status == 'active'
    
    def assign_staff(self, staff_user):
        # Clear this staff from any other window
        ServiceWindow.objects.filter(current_staff=staff_user).update(current_staff=None)
        
        # Assign to this window
        self.current_staff = staff_user
        self.save()
        
        # Update staff profile
        if hasattr(staff_user, 'staff_profile'):
            staff_user.staff_profile.current_window = self
            staff_user.staff_profile.save()


# =======================
# STAFF PROFILE
# =======================
class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('staff', 'Staff Member'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    assigned_service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    can_manage_queue = models.BooleanField(default=True)

    last_login_at = models.DateTimeField(null=True, blank=True)
    last_logout_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'

    def __str__(self):
        service_name = self.assigned_service.name if self.assigned_service else "No Service"
        return f"{self.user.username} - {service_name}"

    def set_current_window(self, window_id):
        # Set the window this staff is currently manning
        try:
            window = ServiceWindow.objects.get(
                id = window_id,
                service = self.assigned_service,
                status = 'active'
            )

            # Clear previous staff from this window
            ServiceWindow.objects.filter(current_staff=self.user).update(current_staff=None)

            # Assign this staff to new window
            window.current_staff = self.user
            window.save()

            # Update profile
            self.current_window = window
            self.save()
            
            return window
        except ServiceWindow.DoesNotExist:
            return None
        
    def clear_current_window(self):
        if self.current_window:
            self.current_window.current_staff = None
            self.current_window.save()
            self.current_window = None
            self.save()


# =======================
# TICKET MODEL
# =======================
class Ticket(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('notified', 'Notified'),
        ('serving', 'Currently Serving'),
        ('served', 'Served'),
        ('cancelled', 'Cancelled'),
        ('skipped', 'Skipped'),
    ]

    ticket_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='tickets')
    queue_number = models.PositiveIntegerField(default=0)
    display_number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')

    assigned_window = models.ForeignKey(
        ServiceWindow,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets'
    )

    ticket_date = models.DateField(default=timezone.now)

    called_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='called_tickets')
    served_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='served_tickets')

    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    skipped_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['service', 'ticket_date', 'queue_number']
        unique_together = ['service', 'queue_number', 'ticket_date']
        indexes = [
            models.Index(fields=['status', 'ticket_date']),
            models.Index(fields=['service', 'status']),
            models.Index(fields=['assigned_window', 'status']),
        ]

    def __str__(self):
        return f"{self.service.name} - {self.display_number}"

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.ticket_date = timezone.now().date()
            self.queue_number = self.service.get_next_queue_number()
            self.display_number = self.service.get_display_number(self.queue_number)

        super().save(*args, **kwargs)

    @property
    def people_ahead(self):
        if self.status in ['serving', 'served', 'cancelled', 'skipped']:
            return 0

        return Ticket.objects.filter(
            service=self.service,
            ticket_date=self.ticket_date,
            status__in=['waiting', 'notified'],
            queue_number__lt=self.queue_number
        ).count()

    @property
    def is_today(self):
        return self.ticket_date == timezone.now().date()

    @property
    def wait_time_minutes(self):
        if self.status in ['served', 'cancelled', 'skipped']:
            return 0
        return self.people_ahead * self.service.average_service_time


# =======================
# POST MIGRATE INITIAL DATA
# =======================
@receiver(post_migrate)
def create_initial_data(sender, **kwargs):
    if sender.name != 'queueing':
        return

    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@school.edu',
            'first_name': 'System',
            'last_name': 'Administrator',
            'is_superuser': True,
            'is_staff': True
        }
    )

    if created:
        admin_user.set_password('admin123')
        admin_user.save()

    StaffProfile.objects.get_or_create(user=admin_user, defaults={'role': 'admin'})
