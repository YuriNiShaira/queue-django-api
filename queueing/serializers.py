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
    waiting_count = serializers.IntegerField(read_only=True)
    currently_serving = serializers.SerializerMethodField()
    windows = ServiceWindowSerializer(many=True, read_only=True)
    windows_count = serializers.IntegerField(source='windows.count', read_only=True)
    
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'prefix',
            'is_active', 'average_service_time',
            'current_queue_number', 'waiting_count',
            'currently_serving', 'windows', 'windows_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_queue_number', 'created_at', 'updated_at']
    
    def get_currently_serving(self, obj):
        serving = obj.currently_serving
        if serving:
            return {
                'ticket_id': str(serving.ticket_id),
                'display_number': serving.display_number,
                'queue_number': serving.queue_number,
                'assigned_window': ServiceWindowSerializer(serving.assigned_window).data if serving.assigned_window else None
            }
        return None

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