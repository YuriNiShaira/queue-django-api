from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta
from .models import Service, Ticket
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from datetime import datetime, timedelta
import csv
from django.http import HttpResponse

@extend_schema(
    tags=['Admin Analytics'],
    summary='Get admin dashboard analytics',
    description='Returns comprehensive analytics including total tickets, average wait times, peak hours, and recent activity.',
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Analytics data retrieved successfully",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'analytics': {
                            'date': '2024-03-17',
                            'summary': {
                                'total_tickets_issued': 150,
                                'total_tickets_served': 120,
                                'completion_rate': 80.0,
                                'currently_waiting': 25,
                                'currently_serving': 5
                            },
                            'services': [
                                {
                                    'service_id': 1,
                                    'service_name': 'Cashier',
                                    'prefix': 'C',
                                    'tickets_today': 50,
                                    'served_today': 40,
                                    'waiting_now': 8,
                                    'serving_now': 2,
                                    'average_wait_minutes': 4.5,
                                    'estimated_total_wait': 32
                                }
                            ],
                            'peak_hours': [
                                {'hour': '10:00', 'tickets_issued': 25},
                                {'hour': '11:00', 'tickets_issued': 22}
                            ],
                            'recent_activity': [
                                {
                                    'ticket': 'C045',
                                    'service': 'Cashier',
                                    'served_at': '14:30:25',
                                    'wait_time': 3.5
                                }
                            ],
                            'timestamp': '2024-03-17T14:30:45.123Z'
                        }
                    }
                )
            ]
        ),
        401: OpenApiResponse(description="❌ Unauthorized - Admin access required"),
        403: OpenApiResponse(description="❌ Forbidden - Insufficient permissions")
    }
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics(request):
    """Get analytics data for admin dashboard with date filtering"""
    today = timezone.now().date()

    date_param = request.GET.get("date")
    start_date_param = request.GET.get("start_date")
    end_date_param = request.GET.get("end_date")

    try:
        if date_param:
            selected_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            tickets = Ticket.objects.filter(ticket_date=selected_date)
            date_label = str(selected_date)

        elif start_date_param and end_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()

            if start_date > end_date:
                return Response(
                    {"success": False, "message": "start_date cannot be greater than end_date"},
                    status=400
                )

            tickets = Ticket.objects.filter(ticket_date__range=[start_date, end_date])
            date_label = f"{start_date} to {end_date}"

        else:
            tickets = Ticket.objects.filter(ticket_date=today)
            date_label = str(today)

    except ValueError:
        return Response(
            {"success": False, "message": "Invalid date format. Use YYYY-MM-DD."},
            status=400
        )

    total_tickets = tickets.count()
    served_total = tickets.filter(status='served').count()
    waiting_total = tickets.filter(status='waiting').count()
    serving_total = tickets.filter(status='serving').count()

    services_data = []
    for service in Service.objects.all():
        service_tickets = tickets.filter(service=service)
        served_tickets = service_tickets.filter(status='served')

        wait_times = []
        for ticket in served_tickets:
            if ticket.called_at and ticket.created_at:
                wait_time = (ticket.called_at - ticket.created_at).total_seconds() / 60
                wait_times.append(wait_time)

        avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0

        services_data.append({
            'service_id': service.id,
            'service_name': service.name,
            'prefix': service.prefix,
            'tickets': service_tickets.count(),
            'served': served_tickets.count(),
            'waiting': service_tickets.filter(status='waiting').count(),
            'serving': service_tickets.filter(status='serving').count(),
            'average_wait_minutes': round(avg_wait, 1),
            'estimated_total_wait': service_tickets.filter(status='waiting').count() * service.average_service_time
        })

    peak_hours = []
    for hour in range(0, 24):
        hour_count = tickets.filter(created_at__hour=hour).count()
        if hour_count > 0:
            peak_hours.append({
                'hour': f'{hour:02d}:00',
                'tickets_issued': hour_count
            })

    peak_hours.sort(key=lambda x: x['tickets_issued'], reverse=True)

    recent_served = tickets.filter(status='served').order_by('-served_at')[:10]
    recent_activity = []

    for ticket in recent_served:
        recent_activity.append({
            'ticket': ticket.display_number,
            'service': ticket.service.name,
            'served_at': ticket.served_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.served_at else None,
            'wait_time': round(
                (ticket.called_at - ticket.created_at).total_seconds() / 60, 1
            ) if ticket.called_at and ticket.created_at else 0
        })

    return Response({
        'success': True,
        'analytics': {
            'date': date_label,
            'summary': {
                'total_tickets_issued': total_tickets,
                'total_tickets_served': served_total,
                'completion_rate': round((served_total / total_tickets * 100), 1) if total_tickets > 0 else 0,
                'currently_waiting': waiting_total,
                'currently_serving': serving_total
            },
            'services': services_data,
            'peak_hours': peak_hours[:5],
            'recent_activity': recent_activity,
            'timestamp': timezone.now().isoformat()
        }
    })

@extend_schema(
    tags=['Admin Analytics'],
    summary='Get service-specific analytics',
    description='Returns detailed analytics for a specific service including daily stats and window performance.',
    parameters=[
        OpenApiParameter(
            name='service_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description='ID of the service to get analytics for',
            required=True
        )
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="✅ Service analytics retrieved successfully",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'analytics': {
                            'service': {
                                'id': 1,
                                'name': 'Cashier',
                                'prefix': 'C'
                            },
                            'daily_stats': [
                                {
                                    'date': '2024-03-17',
                                    'total': 45,
                                    'served': 38,
                                    'cancelled': 2
                                }
                            ],
                            'window_performance': [
                                {
                                    'window_id': 6,
                                    'window_name': 'Cashier Window 6',
                                    'window_number': 6,
                                    'tickets_served': 15,
                                    'currently_serving': True
                                },
                                {
                                    'window_id': 7,
                                    'window_name': 'Cashier Window 7',
                                    'window_number': 7,
                                    'tickets_served': 23,
                                    'currently_serving': False
                                }
                            ],
                            'average_service_time': 4,
                            'total_waiting_today': 5
                        }
                    }
                )
            ]
        ),
        401: OpenApiResponse(description="❌ Unauthorized - Admin access required"),
        403: OpenApiResponse(description="❌ Forbidden - Insufficient permissions"),
        404: OpenApiResponse(description="❌ Service not found")
    }
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def service_analytics(request, service_id):
    """Get detailed analytics for a specific service"""
    try:
        service = Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        return Response({'success': False, 'message': 'Service not found'}, status=404)
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    # Last 7 days data
    daily_stats = []
    for i in range(7):
        day = today - timedelta(days=i)
        day_tickets = Ticket.objects.filter(
            service=service, 
            ticket_date=day
        )

        daily_stats.append({
            'date': day,
            'total': day_tickets.count(),
            'served': day_tickets.filter(status='served').count(),
            'cancelled': day_tickets.filter(status='cancelled').count()
        })

    # Window performance with window_number added
    window_stats = []
    for window in service.windows.all():
        window_tickets = Ticket.objects.filter(
            assigned_window=window, 
            ticket_date=today
        )

        window_stats.append({
            'window_id': window.id,
            'window_name': window.name,
            'window_number': window.window_number, 
            'tickets_served': window_tickets.filter(status='served').count(),
            'currently_serving': window_tickets.filter(status='serving').exists()
        })

    return Response({
        'success': True,
        'analytics': {
            'service': {
                'id': service.id,
                'name': service.name,
                'prefix': service.prefix
            },
            'daily_stats': daily_stats,
            'window_performance': window_stats,
            'average_service_time': service.average_service_time,
            'total_waiting_today': service.waiting_count
        }
    })



@extend_schema(
    tags=['Admin Analytics'],
    summary='Get window analytics',
    description='Returns per-window analytics for a specific service',
    parameters=[
        OpenApiParameter(
            name='service_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description='ID of the service',
            required=True
        ),
        OpenApiParameter(
            name='start_date',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Filter by start date (YYYY-MM-DD)',
            required=False
        ),
        OpenApiParameter(
            name='end_date',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Filter by end date (YYYY-MM-DD)',
            required=False
        ),
    ]
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def window_analytics(request, service_id):
    """Get detailed per-window analytics for a specific service"""
    try:
        service = Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        return Response({'success': False, 'message': 'Service not found'}, status=404)
    
    # Date filtering
    start_date_param = request.GET.get("start_date")
    end_date_param = request.GET.get("end_date")
    
    try:
        if start_date_param and end_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
            tickets = Ticket.objects.filter(
                ticket_date__range=[start_date, end_date],
                service=service
            )
            date_label = f"{start_date} to {end_date}"
        elif start_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            tickets = Ticket.objects.filter(ticket_date=start_date, service=service)
            date_label = str(start_date)
        elif end_date_param:
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
            tickets = Ticket.objects.filter(ticket_date=end_date, service=service)
            date_label = str(end_date)
        else:
            today = timezone.now().date()
            tickets = Ticket.objects.filter(ticket_date=today, service=service)
            date_label = str(today)
    except ValueError:
        return Response(
            {"success": False, "message": "Invalid date format. Use YYYY-MM-DD."},
            status=400
        )
    
    window_stats = []
    for window in service.windows.all():
        window_tickets = tickets.filter(assigned_window=window)
        served_tickets = window_tickets.filter(status='served')
        
        # Calculate average wait time for this window
        wait_times = []
        for ticket in served_tickets:
            if ticket.called_at and ticket.created_at:
                wait_time = (ticket.called_at - ticket.created_at).total_seconds() / 60
                wait_times.append(wait_time)
        
        avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
        
        # Daily breakdown for this window
        daily_breakdown = []
        if not start_date_param and not end_date_param:
            # Just show today
            daily_breakdown.append({
                'date': str(today),
                'served': served_tickets.filter(ticket_date=today).count(),
                'cancelled': window_tickets.filter(status='cancelled', ticket_date=today).count(),
                'avg_wait_minutes': round(avg_wait, 1)
            })
        else:
            # Show breakdown by day within range
            date_range = (end_date - start_date).days + 1 if start_date_param and end_date_param else 1
            for i in range(date_range):
                day = (start_date if start_date_param else today) + timedelta(days=i)
                day_tickets = window_tickets.filter(ticket_date=day)
                day_served = day_tickets.filter(status='served')
                
                day_wait_times = []
                for ticket in day_served:
                    if ticket.called_at and ticket.created_at:
                        day_wait_times.append((ticket.called_at - ticket.created_at).total_seconds() / 60)
                
                day_avg_wait = sum(day_wait_times) / len(day_wait_times) if day_wait_times else 0
                
                daily_breakdown.append({
                    'date': str(day),
                    'served': day_served.count(),
                    'cancelled': day_tickets.filter(status='cancelled').count(),
                    'avg_wait_minutes': round(day_avg_wait, 1)
                })
        
        window_stats.append({
            'window_id': window.id,
            'window_name': window.name,
            'window_number': window.window_number,
            'status': window.status,
            'tickets_served': served_tickets.count(),
            'tickets_served_total': window_tickets.filter(status='served').count(),
            'tickets_cancelled': window_tickets.filter(status='cancelled').count(),
            'avg_wait_minutes': round(avg_wait, 1),
            'currently_serving': window_tickets.filter(status='serving').exists(),
            'daily_breakdown': daily_breakdown
        })
    
    # Calculate totals
    total_served = sum(w['tickets_served'] for w in window_stats)
    total_cancelled = sum(w['tickets_cancelled'] for w in window_stats)
    overall_avg_wait = sum(w['avg_wait_minutes'] for w in window_stats) / len(window_stats) if window_stats else 0
    
    return Response({
        'success': True,
        'service': {
            'id': service.id,
            'name': service.name,
            'prefix': service.prefix
        },
        'date_range': date_label,
        'summary': {
            'total_windows': len(window_stats),
            'active_windows': sum(1 for w in window_stats if w['status'] == 'active'),
            'total_served': total_served,
            'total_cancelled': total_cancelled,
            'overall_avg_wait_minutes': round(overall_avg_wait, 1)
        },
        'windows': window_stats
    })


@extend_schema(
    tags=['Admin Analytics'],
    summary='Export analytics to CSV',
    description='Export ticket data as CSV file',
    parameters=[
        OpenApiParameter(
            name='start_date',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Start date (YYYY-MM-DD)',
            required=False
        ),
        OpenApiParameter(
            name='end_date',
            type=str,
            location=OpenApiParameter.QUERY,
            description='End date (YYYY-MM-DD)',
            required=False
        ),
        OpenApiParameter(
            name='service_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Filter by service ID',
            required=False
        ),
        OpenApiParameter(
            name='format',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Export format (csv or excel)',
            required=False
        ),
    ]
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_analytics_csv(request):
    """Export ticket data as CSV file"""
    
    start_date_param = request.GET.get("start_date")
    end_date_param = request.GET.get("end_date")
    service_id = request.GET.get("service_id")

    tickets = Ticket.objects.select_related('service', 'assigned_window', 'called_by', 'served_by')

    try:
        if start_date_param and end_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()

            if start_date > end_date:
                return Response(
                    {"success": False, "message": "start_date cannot be later than end_date."},
                    status=400
                )

            tickets = tickets.filter(ticket_date__range=[start_date, end_date])

        elif start_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            tickets = tickets.filter(ticket_date__gte=start_date)

        elif end_date_param:
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
            tickets = tickets.filter(ticket_date__lte=end_date)

        else:
            # default to today if no filters are provided
            today = timezone.now().date()
            tickets = tickets.filter(ticket_date=today)

    except ValueError:
        return Response(
            {"success": False, "message": "Invalid date format. Use YYYY-MM-DD."},
            status=400
        )

    if service_id:
        tickets = tickets.filter(service_id=service_id)

    response = HttpResponse(content_type='text/csv')
    filename = f"queuick_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\uFEFF')

    writer = csv.writer(response)

    writer.writerow([
        'Ticket Number', 'Service', 'Window', 'Status',
        'Created At', 'Called At', 'Served At',
        'Wait Time (minutes)', 'Ticket Date'
    ])

    for ticket in tickets.order_by('ticket_date', 'created_at'):
        wait_time = 0
        if ticket.called_at and ticket.created_at:
            wait_time = round((ticket.called_at - ticket.created_at).total_seconds() / 60, 1)

        writer.writerow([
            ticket.display_number,
            ticket.service.name if ticket.service else '',
            ticket.assigned_window.name if ticket.assigned_window else 'Not Assigned',
            ticket.status,
            ticket.created_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.created_at else '',
            ticket.called_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.called_at else '',
            ticket.served_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.served_at else '',
            wait_time,
            ticket.ticket_date.strftime('%Y-%m-%d') if ticket.ticket_date else '',
        ])

    return response


@extend_schema(
    tags=['Admin Analytics'],
    summary='Export window performance to CSV',
    description='Export window performance data as CSV file',
    parameters=[
        OpenApiParameter(
            name='service_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description='ID of the service',
            required=True
        ),
        OpenApiParameter(
            name='start_date',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Start date (YYYY-MM-DD)',
            required=False
        ),
        OpenApiParameter(
            name='end_date',
            type=str,
            location=OpenApiParameter.QUERY,
            description='End date (YYYY-MM-DD)',
            required=False
        ),
    ]
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_window_performance_csv(request, service_id):
    """Export window performance data as CSV"""

    try:
        service = Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        return Response({'success': False, 'message': 'Service not found'}, status=404)

    start_date_param = request.GET.get("start_date")
    end_date_param = request.GET.get("end_date")

    try:
        if start_date_param and end_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()

            if start_date > end_date:
                return Response(
                    {"success": False, "message": "start_date cannot be later than end_date."},
                    status=400
                )

            date_label = f"{start_date} to {end_date}"

        elif start_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = start_date
            date_label = str(start_date)

        elif end_date_param:
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
            start_date = end_date
            date_label = str(end_date)

        else:
            today = timezone.now().date()
            start_date = today
            end_date = today
            date_label = str(today)

    except ValueError:
        return Response(
            {"success": False, "message": "Invalid date format. Use YYYY-MM-DD."},
            status=400
        )

    response = HttpResponse(content_type='text/csv')
    filename = f"window_performance_{service.name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\uFEFF')

    writer = csv.writer(response)

    writer.writerow([
        'Service',
        'Date Range',
        'Window Name',
        'Window Number',
        'Status',
        'Tickets Served',
        'Tickets Cancelled',
        'Avg Wait Time (minutes)',
        'Currently Serving'
    ])

    for window in service.windows.all():
        range_tickets = Ticket.objects.filter(
            assigned_window=window,
            ticket_date__range=[start_date, end_date]
        )

        served_tickets = range_tickets.filter(status='served')
        cancelled_tickets = range_tickets.filter(status='cancelled')
        serving_exists = range_tickets.filter(status='serving').exists()

        wait_times = []
        for ticket in served_tickets:
            if ticket.called_at and ticket.created_at:
                wait_times.append((ticket.called_at - ticket.created_at).total_seconds() / 60)

        avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0

        writer.writerow([
            service.name,
            date_label,
            window.name,
            window.window_number,
            window.status,
            served_tickets.count(),
            cancelled_tickets.count(),
            round(avg_wait, 1),
            'Yes' if serving_exists else 'No'
        ])

    return response