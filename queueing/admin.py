from django.contrib import admin
from django.contrib.auth.models import User
from .models import Service, ServiceWindow, Ticket, StaffProfile
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


# =======================
# STAFF PROFILE INLINE
# =======================
class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False
    verbose_name_plural = 'Staff Profile'
    fk_name = 'user'
    fields = ('role', 'assigned_service', 'can_manage_queue')


# =======================
# CUSTOM USER ADMIN
# =======================
class UserAdmin(BaseUserAdmin):
    inlines = (StaffProfileInline,)
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'is_staff', 'is_superuser', 'get_assigned_service'
    )
    list_filter = (
        'is_staff',
        'is_superuser',
        'staff_profile__role',
        'staff_profile__assigned_service'
    )

    def get_assigned_service(self, obj):
        if hasattr(obj, 'staff_profile') and obj.staff_profile.assigned_service:
            return obj.staff_profile.assigned_service.name
        return '-'
    get_assigned_service.short_description = 'Assigned Service'

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# =======================
# SERVICE ADMIN (FIXED)
# =======================
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'prefix',
        'is_active',
        'windows_count',
        'waiting_count',
        'currently_serving_display'
    )
    list_filter = ('is_active', 'created_at')
    list_editable = ('is_active', 'prefix')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Service Information', {
            'fields': ('name', 'description', 'prefix', 'is_active', 'average_service_time')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def windows_count(self, obj):
        return obj.windows.count()
    windows_count.short_description = 'Windows'

    def currently_serving_display(self, obj):
        serving = obj.currently_serving
        return serving.display_number if serving else '-'
    currently_serving_display.short_description = 'Currently Serving'


# =======================
# SERVICE WINDOW ADMIN
# =======================
@admin.register(ServiceWindow)
class ServiceWindowAdmin(admin.ModelAdmin):
    list_display = (
        'service',
        'window_number',
        'name',
        'status',
        'current_staff_display',
        'is_available'
    )
    list_filter = ('status', 'service', 'created_at')
    list_editable = ('status', 'name')
    search_fields = ('service__name', 'name', 'window_number')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Window Information', {
            'fields': ('service', 'window_number', 'name', 'status', 'description')
        }),
        ('Staff Assignment', {
            'fields': ('current_staff',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def current_staff_display(self, obj):
        return obj.current_staff.username if obj.current_staff else '-'
    current_staff_display.short_description = 'Current Staff'

    def is_available(self, obj):
        return obj.is_available
    is_available.boolean = True
    is_available.short_description = 'Available?'


# =======================
# TICKET ADMIN
# =======================
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'display_number',
        'service',
        'status',
        'assigned_window_display',
        'created_at_short',
        'people_ahead',
        'is_today'
    )
    list_filter = ('status', 'service', 'ticket_date', 'created_at', 'assigned_window')
    search_fields = ('display_number', 'ticket_id', 'service__name')
    readonly_fields = (
        'ticket_id',
        'queue_number',
        'display_number',
        'ticket_date',
        'created_at',
        'called_at',
        'served_at',
        'people_ahead_display',
        'wait_time_display'
    )

    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_id', 'service', 'queue_number', 'display_number', 'status', 'ticket_date')
        }),
        ('Window Assignment', {
            'fields': ('assigned_window',),
            'classes': ('collapse',)
        }),
        ('Staff Actions', {
            'fields': ('called_by', 'served_by', 'called_at', 'served_at', 'skipped_at', 'notes')
        }),
        ('Queue Status', {
            'fields': ('people_ahead_display', 'wait_time_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def created_at_short(self, obj):
        return obj.created_at.strftime('%H:%M')
    created_at_short.short_description = 'Time Created'

    def people_ahead(self, obj):
        return obj.people_ahead
    people_ahead.short_description = 'Ahead'

    def is_today(self, obj):
        return obj.is_today
    is_today.boolean = True
    is_today.short_description = 'Today?'

    def assigned_window_display(self, obj):
        if obj.assigned_window:
            return f"{obj.assigned_window.service.name} - {obj.assigned_window.name}"
        return '-'
    assigned_window_display.short_description = 'Assigned Window'

    def people_ahead_display(self, obj):
        return f"{obj.people_ahead} person(s) ahead"
    people_ahead_display.short_description = 'Queue Position'

    def wait_time_display(self, obj):
        return f"{obj.wait_time_minutes} minutes"
    wait_time_display.short_description = 'Estimated Wait'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'service',
            'assigned_window',
            'called_by',
            'served_by'
        )
