from rest_framework import serializers
from .models import Service, Ticket

class ServiceSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    windows_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'display_name', 'description',
            'windows', 'windows_list', 'average_service_time',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_windows_list(self, obj):
        if obj.windows:
            return [w.strip() for w in obj.windows.split(',') if w.strip()]
        return []

class TicketSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.get_name_display', read_only=True)
    display_number = serializers.CharField(source='get_display_number', read_only=True)
    is_today = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Ticket
        fields = [
            'ticket_id', 'queue_number', 'display_number',
            'service', 'service_name', 'status', 'ticket_date',
            'created_at', 'is_today', 'people_ahead'
        ]
        read_only_fields = [
            'ticket_id', 'queue_number', 'display_number',
            'status', 'ticket_date', 'created_at', 'is_today', 'people_ahead'
        ]
    
    def validate_service(self, value):
        """Ensure service is active"""
        if not value.is_active:
            raise serializers.ValidationError("This service is not currently available.")
        return value