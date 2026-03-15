from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import ServiceWindow, Ticket
from .permissions import IsServiceStaff
from .websocket_utils import (
    send_dashboard_update,
    send_service_status_update,
    send_service_update,
    send_ticket_update,
    send_windows_update,
)


def _parse_int(value, field_name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} must be an integer.')


def _complete_serving_ticket(window, served_by=None):
    ticket = Ticket.objects.filter(assigned_window=window, status='serving').first()
    if not ticket:
        return None

    ticket.status = 'served'
    ticket.served_at = timezone.now()
    ticket.served_by = served_by
    ticket.save(update_fields=['status', 'served_at', 'served_by'])
    return str(ticket.ticket_id)


def _broadcast_window_state(service_id, completed_ticket_id=None):
    send_windows_update(service_id)
    send_dashboard_update()
    send_service_update(service_id)
    send_service_status_update(service_id)
    if completed_ticket_id:
        send_ticket_update(completed_ticket_id)


@extend_schema(
    summary='Claim service window',
    description='Marks a window as active and assigned to a staff account.',
    tags=['Active Sessions']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def claim_session(request):
    window_id = request.data.get('window_id')
    staff_account_id = request.data.get('staff_account_id')

    if not window_id or not staff_account_id:
        return Response(
            {
                'error': 'invalid_request',
                'message': 'window_id and staff_account_id are required.',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        window_id = _parse_int(window_id, 'window_id')
        staff_account_id = _parse_int(staff_account_id, 'staff_account_id')
    except ValueError as exc:
        return Response(
            {
                'error': 'invalid_request',
                'message': str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not request.user.is_superuser and request.user.id != staff_account_id:
        return Response(
            {
                'error': 'staff_account_mismatch',
                'message': 'staff_account_id must match the authenticated user.',
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    with transaction.atomic():
        try:
            window = ServiceWindow.objects.select_for_update().select_related('service').get(id=window_id)
        except ServiceWindow.DoesNotExist:
            return Response(
                {
                    'error': 'window_not_found',
                    'message': 'Window not found.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if window.status == 'maintenance':
            return Response(
                {
                    'error': 'window_unavailable',
                    'message': 'Window is under maintenance.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.is_superuser and request.user.staff_profile.assigned_service_id != window.service_id:
            return Response(
                {
                    'error': 'forbidden_window',
                    'message': 'You do not have access to this window.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            staff_account = User.objects.select_related('staff_profile').get(id=staff_account_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {
                    'error': 'staff_account_not_found',
                    'message': 'Staff account not found.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not staff_account.is_superuser:
            if not hasattr(staff_account, 'staff_profile'):
                return Response(
                    {
                        'error': 'staff_profile_missing',
                        'message': 'Staff account does not have a staff profile.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if staff_account.staff_profile.assigned_service_id != window.service_id:
                return Response(
                    {
                        'error': 'service_mismatch',
                        'message': 'Staff account is not assigned to this service.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if window.status == 'active':
            claimed_by = window.current_staff.username if window.current_staff else None
            return Response(
                {
                    'error': 'window_occupied',
                    'message': 'This window is currently in use.',
                    'window': {
                        'id': window.id,
                        'name': window.name,
                        'status': window.status,
                        'claimed_by': claimed_by,
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        window.status = 'active'
        window.current_staff = staff_account
        window.save(update_fields=['status', 'current_staff'])

        window.service.update_active_status()

    _broadcast_window_state(window.service_id)

    return Response(
        {
            'success': True,
            'message': 'Window claimed successfully.',
            'window': {
                'id': window.id,
                'name': window.name,
                'number': window.window_number,
                'status': window.status,
                'current_staff': {
                    'id': staff_account.id,
                    'username': staff_account.username,
                },
            },
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    summary='Release service window',
    description='Marks a window as inactive and clears assigned staff.',
    tags=['Active Sessions']
)
@api_view(['POST'])
@permission_classes([IsServiceStaff])
def release_session(request):
    window_id = request.data.get('window_id')
    if not window_id:
        return Response(
            {
                'error': 'invalid_request',
                'message': 'window_id is required.',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        window_id = _parse_int(window_id, 'window_id')
    except ValueError as exc:
        return Response(
            {
                'error': 'invalid_request',
                'message': str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        try:
            window = ServiceWindow.objects.select_for_update().select_related('service').get(id=window_id)
        except ServiceWindow.DoesNotExist:
            return Response(
                {
                    'error': 'window_not_found',
                    'message': 'Window not found.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not request.user.is_superuser and request.user.staff_profile.assigned_service_id != window.service_id:
            return Response(
                {
                    'error': 'forbidden_window',
                    'message': 'You do not have access to this window.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not request.user.is_superuser and window.current_staff_id and window.current_staff_id != request.user.id:
            return Response(
                {
                    'error': 'session_owner_mismatch',
                    'message': 'Only the assigned staff can release this window.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        completed_ticket_id = _complete_serving_ticket(window, served_by=request.user)

        window.status = 'inactive'
        window.current_staff = None
        window.save(update_fields=['status', 'current_staff'])

        window.service.update_active_status()

    _broadcast_window_state(window.service_id, completed_ticket_id)

    return Response(
        {
            'success': True,
            'message': 'Window released successfully.',
            'window': {
                'id': window.id,
                'name': window.name,
                'number': window.window_number,
                'status': window.status,
                'current_staff': None,
            },
            'completed_ticket_id': completed_ticket_id,
        },
        status=status.HTTP_200_OK,
    )
