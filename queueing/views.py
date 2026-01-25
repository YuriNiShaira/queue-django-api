from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Service, Ticket
from .serializers import ServiceSerializer, TicketSerializer
from .escpos_utils import MockPrinter

class ServiceListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ServiceSerializer
    
    def get_queryset(self):
        return Service.objects.filter(is_active=True).order_by('name')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        response_data = {
            'success': True,
            'count': queryset.count(),
            'services': serializer.data,
            'message': 'Active services retrieved successfully'
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

class GenerateTicketView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = TicketSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        
        # Generate printer data
        print_result = MockPrinter.print_ticket(ticket, save_to_file=True)
        
        import base64
        raw_bytes_base64 = ''
        if print_result.get('raw_bytes'):
            raw_bytes_base64 = base64.b64encode(print_result['raw_bytes']).decode('utf-8')
        
        # Response with daily reset info
        response_data = {
            'success': True,
            'message': f'Ticket #{ticket.get_display_number()} generated for today ({ticket.ticket_date})',
            
            'ticket': {
                'id': str(ticket.ticket_id),
                'service': ticket.service.get_name_display(),
                'service_id': ticket.service.id,
                'queue_number': ticket.queue_number,
                'display_number': ticket.get_display_number(),  # "001"
                'ticket_date': str(ticket.ticket_date),
                'is_today': ticket.is_today,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
                'people_ahead': ticket.people_ahead,
                'total_today': Ticket.objects.filter(
                    service=ticket.service,
                    ticket_date=ticket.ticket_date
                ).count(),
            },
            
            'printer': {
                'success': print_result.get('success', True),
                'preview_html': print_result.get('preview_html', ''),
                'escpos_hex': print_result.get('hex_string', ''),
                'escpos_base64': raw_bytes_base64,
                'bytes_length': print_result.get('length_bytes', 0),
            },
            
            'action': {
                'show_preview': True,
                'auto_print': False,
                'message': f'Printing ticket #{ticket.get_display_number()}...',
            }
        }
        
        if print_result.get('saved_files'):
            response_data['debug'] = {
                'saved_files': print_result['saved_files'],
            }
        
        return Response(response_data, status=status.HTTP_201_CREATED)