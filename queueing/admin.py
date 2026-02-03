from django.contrib import admin
from django.utils import timezone
from .models import Window, Ticket

@admin.register(Window)
class WindowAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'service_type_display', 'status', 'current_queue_number', 'is_active_today')
    list_filter = ('status', 'service_type', 'last_queue_reset')
    list_editable = ('status', 'name')
    search_fields = ('number', 'name', 'service_type')
    readonly_fields = ('current_queue_number', 'last_queue_reset', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Window Information', {
            'fields': ('number', 'name', 'service_type', 'status', 'description')
        }),
        ('Queue Management', {
            'fields': ('current_queue_number', 'last_queue_reset'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def service_type_display(self, obj):
        return obj.get_service_type_display()
    service_type_display.short_description = 'Service Type'
    
    def is_active_today(self, obj):
        return obj.last_queue_reset == timezone.now().date()
    is_active_today.boolean = True
    is_active_today.short_description = 'Active Today?'

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'get_display', 
        'display_service_column', 
        'ticket_date', 
        'status', 
        'created_at_short', 
        'people_ahead', 
        'is_today'
    )
    
    list_filter = (
        'status', 
        'service_group', 
        'ticket_date', 
        'created_at', 
        'window__service_type'
    )
    
    search_fields = (
        'queue_number', 
        'ticket_id', 
        'window__number', 
        'window__name'
    )
    
    readonly_fields = (
        'ticket_id', 
        'queue_number', 
        'ticket_date', 
        'created_at', 
        'called_at', 
        'served_at', 
        'people_ahead_display',
        'display_number',
        'display_service_column'
    )
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_id', 'queue_number', 'display_number', 'ticket_date', 'status')
        }),
        ('Service Assignment', {
            'fields': ('window', 'service_group', 'display_service_column', 'served_window')
        }),
        ('Queue Status', {
            'fields': ('people_ahead_display', 'notified'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'called_at', 'served_at'),
            'classes': ('collapse',)
        }),
    )
    
    # ================= Methods ================= #
    
    def get_display(self, obj):
        return f"#{obj.get_display_number()}"
    get_display.short_description = 'Ticket'
    
    def display_service_column(self, obj):
        return obj.display_service
    display_service_column.short_description = 'Service'
    
    def created_at_short(self, obj):
        return obj.created_at.strftime('%H:%M')
    created_at_short.short_description = 'Time'
    
    def people_ahead(self, obj):
        return obj.people_ahead
    people_ahead.short_description = 'Ahead'
    
    def is_today(self, obj):
        return obj.is_today
    is_today.boolean = True
    is_today.short_description = 'Today?'
    
    def display_number(self, obj):
        return obj.get_display_number()
    display_number.short_description = 'Display Number'
    
    def people_ahead_display(self, obj):
        return f"{obj.people_ahead} person(s) ahead"
    people_ahead_display.short_description = 'Queue Position'
    
    def get_queryset(self, request):
        # Optimize queries by selecting related window and served_window
        return super().get_queryset(request).select_related('window', 'served_window')