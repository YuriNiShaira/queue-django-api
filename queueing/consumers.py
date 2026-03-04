import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import Service, Ticket, ServiceWindow
from .serializers import TicketSerializer
import logging

logger = logging.getLogger(__name__)

class TestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info(f"TestConsumer connect called from {self.scope.get('client')}")
        print(f"TestConsumer connect called from {self.scope.get('client')}")
        print(f" Path: {self.scope.get('path')}")
        print(f" Headers: {self.scope.get('headers')}")
        
        try:
            await self.accept()
            print("TestConsumer connection accepted")
            logger.info("TestConsumer connection accepted")
            
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to test consumer'
            }))
        except Exception as e:
            print(f"Error in connect: {e}")
            logger.error(f"Error in connect: {e}")
    
    async def disconnect(self, close_code):
        print(f"TestConsumer disconnected with code: {close_code}")
        logger.info(f"TestConsumer disconnected with code: {close_code}")
    
    async def receive(self, text_data):
        print(f"TestConsumer received: {text_data}")
        logger.info(f"TestConsumer received: {text_data}")
        await self.send(text_data=json.dumps({
            'echo': text_data
        }))

class DashboardConsumer(AsyncWebsocketConsumer):
    #WebSocket consumer for real-time dashboard updates

    async def connect(self):
        self.group_name = 'public_dashboard'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        await self.send_dashboard_update()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def dashboard_update(self, event):
        """Called when send_dashboard_update() is called"""
        print("=== DASHBOARD UPDATE RECEIVED ===")
        await self.send_dashboard_update()


    async def receive(self, text_data):
        # Client can request refresh
        data = json.loads(text_data)
        if data.get('action') == 'refresh':
            await self.send_dashboard_update()

    async def send_dashboard_update(self):
        #Send dashboard data to client
        data = await self.get_dashboard_data()
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': data
        }))
        
    @database_sync_to_async
    def get_dashboard_data(self):
        #"Get current dashboard data (same as dashboard_status view)
        services = Service.objects.filter(is_active=True).order_by('name')

        service_data = []
        for service in services:
            today = timezone.now().date()
            tickets_today = service.tickets.filter(ticket_date = today)

            # Get ALL currently serving tickets with window info
            serving_tickets = tickets_today.filter(status='serving').select_related('assigned_window').order_by('assigned_window__window_number')

            currently_serving_list =[]
            for ticket in serving_tickets:
                if ticket.assigned_window:
                    currently_serving_list.append({
                        'ticket_number': ticket.display_number,
                        'window_name': ticket.assigned_window.name,
                        'window_number': ticket.assigned_window.window_number
                    })

            # Get waiting tickets
            waiting_tickets = tickets_today.filter(
                status__in=['waiting', 'notified']
            ).order_by('queue_number')

            service_data.append({
                'id': service.id,
                'name': service.name,
                'prefix': service.prefix,
                'currently_serving': currently_serving_list,
                'serving_count': len(currently_serving_list),
                'next_in_line': waiting_tickets.first().display_number if waiting_tickets.exists() else None,
                'waiting_count': waiting_tickets.count(),
            })

        total_waiting = sum(s['waiting_count'] for s in service_data)
        total_serving = sum(s['serving_count'] for s in service_data)

        return {
            'timestamp': timezone.now().isoformat(),
            'summary': {
                'total_waiting': total_waiting,
                'total_serving': total_serving,
                'last_updated': timezone.now().strftime('%I:%M:%S %p')
            },
            'services': service_data
        }
    
    
User = get_user_model()

class StaffDashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for staff dashboard real-time updates
    Each staff only gets updates for their service
    Supports authentication via cookies or manual token
    """
    
    async def connect(self):
        print("=== STAFF DASHBOARD: CONNECT ATTEMPT ===")
        
        # Get service_id from URL
        self.service_id = self.scope['url_route']['kwargs']['service_id']
        
        # Try to authenticate from scope first (cookies)
        self.user = self.scope['user']
        
        if self.user and self.user.is_authenticated:
            print(f"User authenticated via scope: {self.user.username}")
            await self.accept()
            await self.authenticated_connect()
        else:
            print("No authenticated user in scope, waiting for manual auth")
            # Accept connection but wait for auth message
            await self.accept()
    
    async def receive(self, text_data):
        """Handle messages from client"""
        try:
            data = json.loads(text_data)
            print(f"Received message: {data.get('type', 'unknown')}")
            
            # Handle authentication message
            if data.get('type') == 'authenticate':
                await self.handle_authentication(data)
            
            # Handle refresh request
            elif data.get('type') == 'refresh':
                await self.send_staff_update()
            
        except json.JSONDecodeError:
            print("Invalid JSON received")
        except Exception as e:
            print(f"Error in receive: {e}")
    
    async def handle_authentication(self, data):
        """Handle manual authentication via cookies or token"""
        print("=== HANDLING MANUAL AUTHENTICATION ===")
        
        # Method 1: Authenticate via cookies string
        cookies = data.get('cookies', '')
        if cookies:
            print(f"Cookies received: {cookies[:50]}...")  # Log first 50 chars
            self.user = await self.authenticate_from_cookies(cookies)
        
        # Method 2: Authenticate via direct token
        if not self.user and data.get('token'):
            token = data.get('token')
            print("Attempting token authentication")
            self.user = await self.authenticate_from_token(token)
        
        if self.user and self.user.is_authenticated:
            print(f"Manual authentication successful: {self.user.username}")
            await self.authenticated_connect()
        else:
            print("Manual authentication failed")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Authentication failed'
            }))
            await self.close()
    
    @database_sync_to_async
    def authenticate_from_cookies(self, cookie_string):
        """Extract and validate JWT from cookie string"""
        try:
            # Parse cookie string
            cookies = {}
            for item in cookie_string.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key] = value
            
            # Get access token from cookies
            access_token = cookies.get('access_token')
            if not access_token:
                print("No access_token in cookies")
                return None
            
            # Validate token
            token = AccessToken(access_token)
            user_id = token.payload.get('user_id')
            
            if user_id:
                user = User.objects.get(id=user_id)
                if user.is_active:
                    return user
        except TokenError as e:
            print(f"Token error: {e}")
        except User.DoesNotExist:
            print("User not found")
        except Exception as e:
            print(f"Cookie auth error: {e}")
        
        return None
    
    @database_sync_to_async
    def authenticate_from_token(self, token_string):
        """Authenticate using direct JWT token"""
        try:
            token = AccessToken(token_string)
            user_id = token.payload.get('user_id')
            
            if user_id:
                user = User.objects.get(id=user_id)
                if user.is_active:
                    return user
        except TokenError as e:
            print(f"Token error: {e}")
        except User.DoesNotExist:
            print("User not found")
        
        return None
    
    @database_sync_to_async
    def check_service_access(self):
        """Check if user has access to this service"""
        if not self.user:
            return False
        
        # Super admin can access any service
        if self.user.is_superuser:
            return True
        
        # Check if user has staff profile with correct service
        if hasattr(self.user, 'staff_profile'):
            profile = self.user.staff_profile
            if profile.assigned_service and profile.assigned_service.id == int(self.service_id):
                return True
        
        return False
    
    async def authenticated_connect(self):
        """Called after successful authentication"""
        # Verify service access
        has_access = await self.check_service_access()
        
        if not has_access:
            print(f"User {self.user.username} does not have access to service {self.service_id}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You do not have access to this service'
            }))
            await self.close()
            return
        
        # Join service-specific group
        self.group_name = f'service_{self.service_id}'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        print(f"Staff {self.user.username} joined group {self.group_name}")
        
        # Send confirmation
        await self.send(text_data=json.dumps({
            'type': 'connected',
            'message': f'Connected to service {self.service_id} as {self.user.username}',
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'is_staff': self.user.is_staff,
                'is_superuser': self.user.is_superuser
            }
        }))
        
        # Send initial dashboard data
        await self.send_staff_update()
    
    async def disconnect(self, close_code):
        """Handle disconnection"""
        if hasattr(self, 'group_name'):
            print(f"🔌 Staff {getattr(self.user, 'username', 'Unknown')} leaving {self.group_name}")
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def send_staff_update(self):
        """Send staff dashboard data to client"""
        data = await self.get_staff_dashboard_data()
        await self.send(text_data=json.dumps({
            'type': 'staff_update',
            'data': data
        }))
    
    @database_sync_to_async
    def get_staff_dashboard_data(self):
        """Get staff dashboard data"""
        try:
            service = Service.objects.get(id=self.service_id)
            today = timezone.now().date()
            
            # Get queue
            waiting = Ticket.objects.filter(
                service=service,
                ticket_date=today,
                status='waiting'
            ).order_by('queue_number')
            
            # Get serving tickets
            serving = Ticket.objects.filter(
                service=service,
                ticket_date=today,
                status='serving'
            ).select_related('assigned_window')
            
            # Get per-window status
            windows_status = []
            for window in service.windows.filter(status='active'):
                window_serving = serving.filter(assigned_window=window).first()
                windows_status.append({
                    'id': window.id,
                    'name': window.name,
                    'number': window.window_number,
                    'currently_serving': window_serving.display_number if window_serving else None
                })
            
            return {
                'service': {
                    'id': service.id,
                    'name': service.name,
                    'prefix': service.prefix
                },
                'waiting_count': waiting.count(),
                'serving_count': serving.count(),
                'next_ticket': waiting.first().display_number if waiting.exists() else None,
                'waiting_list': TicketSerializer(waiting[:10], many=True).data,
                'serving_list': TicketSerializer(serving, many=True).data,
                'windows': windows_status,
                'timestamp': timezone.now().isoformat()
            }
        except Service.DoesNotExist:
            return {'error': 'Service not found'}
    
    # Handler for group messages
    async def queue_update(self, event):
        #Called when there's a queue update
        print(f"=== QUEUE UPDATE RECEIVED for service {self.service_id} ===")
        await self.send_staff_update()

class TicketStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.group_name = f'ticket_{self.ticket_id}'
        
        print(f"🔌 CONSUMER: Connecting for ticket: {self.ticket_id}")
        print(f"🔌 CONSUMER: Group name: {self.group_name}")
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        print(f"✅ CONSUMER: Connection accepted for {self.ticket_id}")
        
        # Send initial status
        await self.send_ticket_status()
    
    async def disconnect(self, close_code):
        print(f"🔌 CONSUMER: Disconnecting for ticket: {self.ticket_id}")
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def ticket_update(self, event):
        """Called when send_ticket_update() is called"""
        print(f"🎯 CONSUMER: TICKET UPDATE RECEIVED for {self.ticket_id}")
        print(f"🎯 CONSUMER: Event: {event}")
        print(f"🎯 CONSUMER: Current channel: {self.channel_name}")
        print(f"🎯 CONSUMER: Current group: {self.group_name}")
        await self.send_ticket_status()
    
    @database_sync_to_async
    def get_ticket_data(self):
        """Get ticket status with current queue position"""
        try:
            from .serializers import TicketSerializer
            print(f"📊 CONSUMER: Fetching data for ticket {self.ticket_id}")
            ticket = Ticket.objects.get(ticket_id=self.ticket_id)
            
            data = TicketSerializer(ticket).data
            
            # Add queue info
            data['queue_info'] = {
                'position': ticket.people_ahead + 1,
                'total_ahead': ticket.people_ahead,
                'estimated_wait_minutes': ticket.wait_time_minutes,
                'total_in_queue': Ticket.objects.filter(
                    service=ticket.service,
                    ticket_date=ticket.ticket_date,
                    status__in=['waiting', 'notified']
                ).count()
            }
            
            print(f"📊 CONSUMER: Data fetched for {ticket.display_number}")
            return data
        except Ticket.DoesNotExist:
            print(f"❌ CONSUMER: Ticket {self.ticket_id} not found!")
            return None
    
    async def send_ticket_status(self):
        """Send ticket status to client"""
        print(f"📤 CONSUMER: Sending ticket status for {self.ticket_id}")
        data = await self.get_ticket_data()
        if data:
            await self.send(text_data=json.dumps({
                'type': 'ticket_update',
                'data': data
            }))
            print(f"✅ CONSUMER: Status sent for {self.ticket_id}")
        else:
            print(f"❌ CONSUMER: No data found for ticket {self.ticket_id}")

#  daphne -b 0.0.0.0 -p 8000 backend.asgi:application