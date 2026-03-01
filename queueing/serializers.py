# queueing/serializers.py
from rest_framework import serializers
from .models import Service, ServiceWindow, Ticket
from django.contrib.auth.models import User

class ServiceWindowSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    current_staff_name = serializers.CharField(source='current_staff.username', read_only=True, allow_null=True)
    
    class Meta:
        model = ServiceWindow
        fields = [
            'id', 'service', 'service_name', 'window_number', 'name',
            'status', 'description', 'current_staff', 'current_staff_name',
            'is_available', 'created_at', 'updated_at'
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

    def get_currently_serving(self, obj):
        serving = obj.currently_serving
        return serving.display_number if serving else None
    
    def validate_prefix(self, value):
        if value:
            queryset = Service.objects.filter(prefix = value)

            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise serializers.ValidationError('Prefix already exists, Please use a unique prefix')

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