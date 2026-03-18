from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import timedelta

from .models import Service, ServiceWindow, StaffProfile, Ticket


class WindowSessionApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.service = Service.objects.create(name='Cashier', prefix='C')
        self.window = ServiceWindow.objects.create(
            service=self.service,
            window_number=1,
            name='Window 1',
            status='inactive',
        )
        self.primary_staff = User.objects.create_user(
            username='staff_one',
            password='password123',
            is_staff=True,
        )
        self.secondary_staff = User.objects.create_user(
            username='staff_two',
            password='password123',
            is_staff=True,
        )

        StaffProfile.objects.create(user=self.primary_staff, assigned_service=self.service)
        StaffProfile.objects.create(user=self.secondary_staff, assigned_service=self.service)

    def test_claim_active_window_assigns_staff(self):
        self.window.status = 'active'
        self.window.save(update_fields=['status'])

        self.client.force_authenticate(user=self.primary_staff)

        response = self.client.post(
            '/api/sessions/claim',
            {
                'window_id': self.window.id,
                'staff_account_id': self.primary_staff.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.window.refresh_from_db()
        self.assertEqual(self.window.status, 'active')
        self.assertEqual(self.window.current_staff_id, self.primary_staff.id)

    def test_claim_active_window_by_other_staff_returns_409(self):
        self.window.status = 'active'
        self.window.current_staff = self.secondary_staff
        self.window.save(update_fields=['status', 'current_staff'])

        self.client.force_authenticate(user=self.primary_staff)
        response = self.client.post(
            '/api/sessions/claim',
            {
                'window_id': self.window.id,
                'staff_account_id': self.primary_staff.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error'], 'window_occupied')

    def test_claim_active_unclaimed_window_succeeds(self):
        self.window.status = 'active'
        self.window.current_staff = None
        self.window.save(update_fields=['status', 'current_staff'])

        self.client.force_authenticate(user=self.primary_staff)
        response = self.client.post(
            '/api/sessions/claim',
            {
                'window_id': self.window.id,
                'staff_account_id': self.primary_staff.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.window.refresh_from_db()
        self.assertEqual(self.window.current_staff_id, self.primary_staff.id)

    def test_claim_inactive_window_returns_unavailable(self):
        self.window.status = 'inactive'
        self.window.save(update_fields=['status'])

        self.client.force_authenticate(user=self.primary_staff)
        response = self.client.post(
            '/api/sessions/claim',
            {
                'window_id': self.window.id,
                'staff_account_id': self.primary_staff.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'window_unavailable')

    def test_release_clears_window_claim_and_completes_ticket(self):
        self.window.status = 'active'
        self.window.current_staff = self.primary_staff
        self.window.save(update_fields=['status', 'current_staff'])

        ticket = Ticket.objects.create(
            service=self.service,
            status='serving',
            assigned_window=self.window,
            called_by=self.primary_staff,
        )

        self.client.force_authenticate(user=self.primary_staff)
        response = self.client.post(
            '/api/sessions/release',
            {'window_id': self.window.id},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.window.refresh_from_db()
        ticket.refresh_from_db()

        self.assertEqual(self.window.status, 'active')
        self.assertIsNone(self.window.current_staff)
        self.assertEqual(ticket.status, 'served')
        self.assertIsNotNone(ticket.served_at)


class TicketScheduleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.now_time = timezone.localtime().time().replace(second=0, microsecond=0)

    def test_generate_ticket_within_schedule_succeeds(self):
        now_dt = timezone.localtime().replace(second=0, microsecond=0)
        start_dt = now_dt - timedelta(hours=1)
        cutoff_dt = now_dt + timedelta(hours=1)

        service = Service.objects.create(
            name='Registrar',
            prefix='R',
            is_active=True,
            auto_schedule_enabled=True,
            auto_start_time=start_dt.time(),
            auto_cutoff_time=cutoff_dt.time(),
        )

        response = self.client.post(
            '/api/tickets/generate/',
            {'service_id': service.id},
            format='json',
        )

        self.assertEqual(response.status_code, 201)

    def test_generate_ticket_outside_schedule_fails(self):
        now_dt = timezone.localtime().replace(second=0, microsecond=0)
        start_dt = now_dt + timedelta(hours=1)
        cutoff_dt = now_dt + timedelta(hours=2)

        service = Service.objects.create(
            name='Accounting',
            prefix='A',
            is_active=True,
            auto_schedule_enabled=True,
            auto_start_time=start_dt.time(),
            auto_cutoff_time=cutoff_dt.time(),
        )

        response = self.client.post(
            '/api/tickets/generate/',
            {'service_id': service.id},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('outside its ticketing hours', response.data['message'])
