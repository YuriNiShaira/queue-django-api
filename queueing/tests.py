from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

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

    def test_claim_inactive_window_activates_it(self):
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

    def test_claim_active_window_without_staff_returns_409(self):
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

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error'], 'window_occupied')

    def test_release_sets_window_inactive_and_completes_ticket(self):
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

        self.assertEqual(self.window.status, 'inactive')
        self.assertIsNone(self.window.current_staff)
        self.assertEqual(ticket.status, 'served')
        self.assertIsNotNone(ticket.served_at)
