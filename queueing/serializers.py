# queueing/serializers.py
from rest_framework import serializers
from .models import Service, ServiceWindow, Ticket
from django.contrib.auth.models import User

class ServiceWindowSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    is_in_use = serializers.BooleanField(read_only=True)
    current_staff_name = serializers.CharField(source='current_staff.username', read_only=True, allow_null=True)
    
    class Meta:
        model = ServiceWindow
        fields = [
            'id', 'service', 'service_name', 'window_number', 'name',
            'status', 'description', 'current_staff', 'current_staff_name',
            'is_available', 'is_in_use', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class ServiceSerializer(serializers.ModelSerializer):
    windows_count = serializers.IntegerField(read_only=True)
    waiting_count = serializers.IntegerField(read_only=True)
    currently_serving = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            'id',
            'name',
            'description',
            'prefix',
            'is_active',
            'auto_schedule_enabled',
            'auto_start_time',
            'auto_cutoff_time',
            'average_service_time',
            'windows_count',
            'waiting_count',
            'currently_serving',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'windows_count',
            'waiting_count',
            'currently_serving',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'prefix': {
                'allow_blank': False,
                'required': True,
                'trim_whitespace': True
            }
        }

    def validate_prefix(self, value):
        #Validate that prefix is unique
        # Check if prefix already exists
        queryset = Service.objects.filter(prefix=value)
        
        # Exclude current instance if updating
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError('Prefix already exists. Please use a unique prefix.')
        
        return value

    def validate(self, attrs):
        auto_schedule_enabled = attrs.get('auto_schedule_enabled')
        auto_start_time = attrs.get('auto_start_time')
        auto_cutoff_time = attrs.get('auto_cutoff_time')

        if self.instance:
            if auto_schedule_enabled is None:
                auto_schedule_enabled = self.instance.auto_schedule_enabled
            if auto_start_time is None:
                auto_start_time = self.instance.auto_start_time
            if auto_cutoff_time is None:
                auto_cutoff_time = self.instance.auto_cutoff_time

        if auto_schedule_enabled:
            if not auto_start_time or not auto_cutoff_time:
                raise serializers.ValidationError('auto_start_time and auto_cutoff_time are required when auto_schedule_enabled is true.')
            if auto_start_time == auto_cutoff_time:
                raise serializers.ValidationError('auto_start_time and auto_cutoff_time cannot be the same.')

        return attrs

    def get_currently_serving(self, obj):
        serving = obj.currently_serving
        return serving.display_number if serving else None

class TicketSerializer(serializers.ModelSerializer):
    display_number = serializers.CharField(read_only=True)
    is_today = serializers.BooleanField(read_only=True)
    people_ahead = serializers.IntegerField(read_only=True)
    wait_time_minutes = serializers.IntegerField(read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    assigned_window_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'ticket_id', 'queue_number', 'display_number',
            'service', 'service_name', 'status', 'ticket_date',
            'assigned_window', 'assigned_window_info',
            'called_by', 'served_by', 'called_at', 'served_at',
            'created_at', 'is_today', 'people_ahead', 'wait_time_minutes',
            'notes'
        ]
        read_only_fields = [
            'ticket_id', 'queue_number', 'display_number',
            'ticket_date', 'created_at', 'is_today',
            'people_ahead', 'wait_time_minutes'
        ]
    
    def get_assigned_window_info(self, obj):
        if obj.assigned_window:
            return {
                'id': obj.assigned_window.id,
                'name': obj.assigned_window.name,
                'window_number': obj.assigned_window.window_number
            }
        return None

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'assigned_window']
        read_only_fields = ['id', 'is_staff']