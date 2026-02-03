# queueing/serializers.py
from rest_framework import serializers
from .models import Service, Ticket, Window

class WindowSerializer(serializers.ModelSerializer):
    service_display = serializers.CharField(source='get_service_type_display', read_only=True)
    
    class Meta:
        model = Window
        fields = [
            'id', 'number', 'name', 'service_type', 'service_display',
            'status', 'description', 'current_queue_number'
        ]

class ServiceSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    windows_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'display_name', 'description',
            'windows_list', 'average_service_time', 'is_active',
            'current_queue_number', 'last_queue_reset'
        ]
    
    def get_windows_list(self, obj):
        return obj.get_windows_list()

class TicketSerializer(serializers.ModelSerializer):
    display_number = serializers.CharField(source='get_display_number', read_only=True)
    is_today = serializers.BooleanField(read_only=True)
    display_service = serializers.CharField(read_only=True)
    window_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'ticket_id', 'queue_number', 'display_number',
            'window', 'service_group', 'display_service',
            'status', 'ticket_date', 'window_info',
            'created_at', 'is_today', 'people_ahead',
            'called_at', 'served_at', 'notified'
        ]
    
    def get_window_info(self, obj):
        if obj.window:
            return {
                'number': obj.window.number,
                'name': obj.window.name,
                'service_type': obj.window.service_type
            }
        return None
    
    def validate(self, data):
        """Validate ticket creation"""
        # For registrar/permit, window must be specified
        if not data.get('window') and not data.get('service_group'):
            raise serializers.ValidationError(
                "Either window or service_group must be specified"
            )
        
        # For cashier, service_group should be 'cashier'
        if data.get('service_group') == 'cashier' and data.get('window'):
            raise serializers.ValidationError(
                "Cashier tickets should not have a specific window assigned"
            )
        
        # For registrar/permit, window must match service_type
        if data.get('window'):
            window = data['window']
            if data.get('service_group') and data['service_group'] != window.service_type:
                raise serializers.ValidationError(
                    f"Window {window.number} is for {window.get_service_type_display()}, "
                    f"not {data['service_group']}"
                )
        
        return data