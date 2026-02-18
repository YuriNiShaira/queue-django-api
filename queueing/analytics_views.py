from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta
from .models import Service, Ticket

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics(request):
    #Get analytics data for admin dashboard
    today = timezone.now().date()
    
    # ===== TOTAL TICKETS SERVED TODAY =====
    tickets_today = Ticket.objects.filter(ticket_date=today)
    total_tickets = tickets_today.count()
    served_today = tickets_today.filter(status='served').count()
    
    # ===== AVERAGE WAITING TIME PER SERVICE =====
    services_data = []
    for service in Service.objects.all():
        service_tickets_today = tickets_today.filter(service=service)
        
        # Calculate average waiting time for served tickets
        served = service_tickets_today.filter(status='served',called_at__isnull=False)
        
        wait_times = []
        for ticket in served:
            if ticket.called_at and ticket.created_at:
                # Wait time in minutes (called_at - created_at)
                wait_time = (ticket.called_at - ticket.created_at).total_seconds() / 60
                wait_times.append(wait_time)
        
        avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
        
        # Current queue status
        waiting = service_tickets_today.filter(status='waiting').count()
        serving = service_tickets_today.filter(status='serving').count()
        
        services_data.append({
            'service_id': service.id,
            'service_name': service.name,
            'prefix': service.prefix,
            'tickets_today': service_tickets_today.count(),
            'served_today': served.count(),
            'waiting_now': waiting,
            'serving_now': serving,
            'average_wait_minutes': round(avg_wait, 1),
            'estimated_total_wait': waiting * service.average_service_time
        })
    
    # ===== PEAK HOURS (busiest times) =====
    # Group tickets by hour of creation
    peak_hours = []
    for hour in range(7, 19):  # 7 AM to 6 PM
        hour_count = tickets_today.filter(
            created_at__hour=hour
        ).count()
        
        if hour_count > 0:
            peak_hours.append({
                'hour': f'{hour}:00',
                'tickets_issued': hour_count
            })
    
    # Sort by tickets issued (highest first)
    peak_hours.sort(key=lambda x: x['tickets_issued'], reverse=True)
    
    # ===== RECENT ACTIVITY =====
    recent_served = tickets_today.filter(
        status='served'
    ).order_by('-served_at')[:10]
    
    recent_activity = []
    for ticket in recent_served:
        recent_activity.append({
            'ticket': ticket.display_number,
            'service': ticket.service.name,
            'served_at': ticket.served_at.strftime('%H:%M:%S') if ticket.served_at else None,
            'wait_time': (ticket.called_at - ticket.created_at).total_seconds() / 60 if ticket.called_at else 0
        })
    
    return Response({
        'success': True,
        'analytics': {
            'date': today,
            'summary': {
                'total_tickets_issued': total_tickets,
                'total_tickets_served': served_today,
                'completion_rate': round((served_today / total_tickets * 100) if total_tickets > 0 else 0, 1),
                'currently_waiting': tickets_today.filter(status='waiting').count(),
                'currently_serving': tickets_today.filter(status='serving').count()
            },
            'services': services_data,
            'peak_hours': peak_hours[:5],  # Top 5 busiest hours
            'recent_activity': recent_activity,
            'timestamp': timezone.now().isoformat()
        }
    })

