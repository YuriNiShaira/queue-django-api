import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import Service, Ticket, ServiceWindow
from .serializers import TicketSerializer

User = get_user_model()

class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'public_dashboard'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_dashboard_update()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def dashboard_update(self, event):
        await self.send_dashboard_update()

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('action') == 'refresh':
            await self.send_dashboard_update()

    async def send_dashboard_update(self):
        data = await self.get_dashboard_data()
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': data
        }))

    @database_sync_to_async
    def get_dashboard_data(self):
        services = Service.objects.filter(is_active=True).order_by('name')
        service_data = []

        for service in services:
            today = timezone.now().date()
            tickets_today = service.tickets.filter(ticket_date=today)

            serving_tickets = tickets_today.filter(status='serving').select_related('assigned_window').order_by('assigned_window__window_number')
            currently_serving_list = [
                {
                    'ticket_number': ticket.display_number,
                    'window_name': ticket.assigned_window.name,
                    'window_number': ticket.assigned_window.window_number
                }
                for ticket in serving_tickets if ticket.assigned_window
            ]

            waiting_tickets = tickets_today.filter(status__in=['waiting', 'notified']).order_by('queue_number')

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

class StaffDashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.service_id = self.scope['url_route']['kwargs']['service_id']
        self.user = self.scope['user']

        await self.accept()
        if self.user and self.user.is_authenticated:
            await self.authenticated_connect()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get('type') == 'authenticate':
                await self.handle_authentication(data)
            elif data.get('type') == 'refresh':
                await self.send_staff_update()
        except json.JSONDecodeError:
            pass

    async def handle_authentication(self, data):
        cookies = data.get('cookies', '')
        if cookies:
            self.user = await self.authenticate_from_cookies(cookies)
        if not self.user and data.get('token'):
            self.user = await self.authenticate_from_token(data.get('token'))

        if self.user and self.user.is_authenticated:
            await self.authenticated_connect()
        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Authentication failed'
            }))
            await self.close()

    @database_sync_to_async
    def authenticate_from_cookies(self, cookie_string):
        try:
            cookies = dict(item.strip().split('=', 1) for item in cookie_string.split(';') if '=' in item)
            access_token = cookies.get('access_token')
            if not access_token:
                return None
            token = AccessToken(access_token)
            user_id = token.payload.get('user_id')
            if user_id:
                user = User.objects.get(id=user_id)
                if user.is_active:
                    return user
        except Exception:
            return None
        return None

    @database_sync_to_async
    def authenticate_from_token(self, token_string):
        try:
            token = AccessToken(token_string)
            user_id = token.payload.get('user_id')
            if user_id:
                user = User.objects.get(id=user_id)
                if user.is_active:
                    return user
        except Exception:
            return None
        return None

    @database_sync_to_async
    def check_service_access(self):
        if not self.user:
            return False
        if self.user.is_superuser:
            return True
        if hasattr(self.user, 'staff_profile'):
            profile = self.user.staff_profile
            if profile.assigned_service and profile.assigned_service.id == int(self.service_id):
                return True
        return False

    async def authenticated_connect(self):
        has_access = await self.check_service_access()
        if not has_access:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You do not have access to this service'
            }))
            await self.close()
            return

        self.group_name = f'service_{self.service_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)

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

        await self.send_staff_update()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_staff_update(self):
        data = await self.get_staff_dashboard_data()
        await self.send(text_data=json.dumps({
            'type': 'staff_update',
            'data': data
        }))

    @database_sync_to_async
    def get_staff_dashboard_data(self):
        try:
            service = Service.objects.get(id=self.service_id)
            today = timezone.now().date()

            waiting = Ticket.objects.filter(service=service, ticket_date=today, status='waiting').order_by('queue_number')
            serving = Ticket.objects.filter(service=service, ticket_date=today, status='serving').select_related('assigned_window')

            windows_status = []
            for window in service.windows.order_by('window_number'):
                window_serving = serving.filter(assigned_window=window).first()
                windows_status.append({
                    'id': window.id,
                    'name': window.name,
                    'number': window.window_number,
                    'currently_serving': window_serving.display_number if window_serving else None,
                    'status': window.status,
                    'is_available': window.status == 'inactive',
                    'is_in_use': window.status == 'active',
                    'claimed_by': window.current_staff.username if window.current_staff else None,
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

    async def queue_update(self, event):
        await self.send_staff_update()

class TicketStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.group_name = f'ticket_{self.ticket_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_ticket_status()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ticket_update(self, event):
        await self.send_ticket_status()

    @database_sync_to_async
    def get_ticket_data(self):
        try:
            ticket = Ticket.objects.get(ticket_id=self.ticket_id)
            data = TicketSerializer(ticket).data
            data['queue_info'] = {
                'position': ticket.people_ahead + 1,
                'total_ahead': ticket.people_ahead,
                'estimated_wait_minutes': ticket.wait_time_minutes,
                'total_in_queue': Ticket.objects.filter(service=ticket.service, ticket_date=ticket.ticket_date, status__in=['waiting', 'notified']).count()
            }
            return data
        except Ticket.DoesNotExist:
            return None

    async def send_ticket_status(self):
        data = await self.get_ticket_data()
        if data:
            await self.send(text_data=json.dumps({
                'type': 'ticket_update',
                'data': data
            }))


class WindowConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.window_id = int(self.scope['url_route']['kwargs']['window_id'])
        info = await self.get_window_info()
        if not info:
            await self.close(code=4404)
            return

        self.service_id = info['service_id']

        await self.accept()

    async def disconnect(self, close_code):
        return

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON payload.',
            }))
            return

        if data.get('type') not in ['reconnect', 'refresh']:
            return

        await self.send(text_data=json.dumps({
            'type': 'reconnect_ack',
            'window_id': self.window_id,
            'status': 'ok',
        }))

    @database_sync_to_async
    def get_window_info(self):
        window = ServiceWindow.objects.filter(id=self.window_id).select_related('service').first()
        if not window:
            return None
        return {'service_id': window.service_id}


class WindowStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.service_id = self.scope['url_route']['kwargs']['service_id']
        self.group_name = f'windows_{self.service_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_window_status()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get('type') == 'refresh':
            await self.send_window_status()

    async def window_status_update(self, event):
        await self.send_window_status()

    @database_sync_to_async
    def get_windows_payload(self):
        windows = ServiceWindow.objects.filter(service_id=self.service_id).select_related('current_staff').order_by('window_number')
        return {
            'service_id': int(self.service_id),
            'windows': [
                {
                    'id': window.id,
                    'name': window.name,
                    'number': window.window_number,
                    'status': window.status,
                    'is_in_use': window.status == 'active',
                    'is_available': window.status == 'inactive',
                    'claimed_by': window.current_staff.username if window.current_staff else None,
                }
                for window in windows
            ],
        }

    async def send_window_status(self):
        payload = await self.get_windows_payload()
        await self.send(text_data=json.dumps({'type': 'window_status_update', 'data': payload}))


class ServiceStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.service_id = self.scope['url_route']['kwargs']['service_id']
        self.group_name = f'service_status_{self.service_id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        
        # Send initial status
        await self.send_service_status()

        async def disconnect(self, close_code):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def service_status_update(self, event):
        #Called when service status changes
        await self.send_service_status()

    @database_sync_to_async
    def get_service_status(self):
        try:
            service = Service.objects.get(id=self.service_id)
            return {
                'service_id': service.id,
                'service_name': service.name,
                'is_active': service.is_active,
                'active_windows_count': service.windows.filter(status='active').count(),
                'total_windows': service.windows.count()
            }
        except Service.DoesNotExist:
            return None
        
    async def send_service_status(self):
        status = await self.get_service_status()
        if status:
            await self.send(text_data=json.dumps({'type': 'service_status', 'data': status}))
