from django.contrib import admin
from django.utils import timezone
from .models import Service, Ticket

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'windows', 'is_active', 'average_service_time')
    list_filter = ('is_active', 'name')
    list_editable = ('is_active', 'average_service_time')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('get_display', 'service', 'ticket_date', 'status', 'created_at_short', 'people_ahead', 'is_today')
    list_filter = ('status', 'service', 'ticket_date', 'created_at')
    search_fields = ('queue_number', 'ticket_id')
    readonly_fields = ('ticket_id', 'queue_number', 'ticket_date', 'created_at', 'called_at', 'served_at')
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_id', 'service', 'queue_number', 'ticket_date', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'called_at', 'served_at'),
            'classes': ('collapse',)
        }),
        ('Service Details', {
            'fields': ('assigned_window', 'notified'),
            'classes': ('collapse',)
        }),
    )
    
    def get_display(self, obj):
        return f"#{obj.get_display_number()}"
    get_display.short_description = 'Ticket'
    
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