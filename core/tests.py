from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .availability import available_slots
from .models import Appointment, Customer, Service


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, datetime.min.time())).replace(
        hour=hour, minute=minute
    )


class SalonTestBase(TestCase):
    def setUp(self):
        # Un día de la semana futuro (evita depender de la hora actual)
        self.day = (timezone.localdate() + timedelta(days=10))
        self.corte = Service.objects.create(name="Corte", duration_minutes=60, price=30000)
        self.tinte = Service.objects.create(name="Tinte", duration_minutes=120, price=90000)
        self.ana = Customer.objects.create(name="Ana", phone="3001112233")


class AvailabilityTests(SalonTestBase):
    def test_empty_day_has_slots_from_8_to_last_possible(self):
        slots = available_slots(self.day, 60)
        self.assertEqual(timezone.localtime(slots[0]).hour, 8)
        # Último inicio posible para 60 min: 19:00 (termina 20:00)
        self.assertEqual(timezone.localtime(slots[-1]).strftime("%H:%M"), "19:00")

    def test_long_service_has_earlier_last_slot(self):
        slots = available_slots(self.day, 120)
        self.assertEqual(timezone.localtime(slots[-1]).strftime("%H:%M"), "18:00")

    def test_booked_block_is_removed_from_slots(self):
        Appointment.objects.create(customer=self.ana, service=self.corte, start=at(self.day, 10))
        times = [timezone.localtime(s).strftime("%H:%M") for s in available_slots(self.day, 60)]
        self.assertNotIn("10:00", times)
        self.assertNotIn("10:30", times)  # se cruzaría con la cita de 10:00-11:00
        self.assertNotIn("09:30", times)  # 09:30-10:30 también se cruza
        self.assertIn("09:00", times)  # 09:00-10:00 termina justo cuando empieza la otra
        self.assertIn("11:00", times)

    def test_cancelled_appointment_frees_the_slot(self):
        Appointment.objects.create(
            customer=self.ana, service=self.corte, start=at(self.day, 10),
            status=Appointment.Status.CANCELLED,
        )
        times = [timezone.localtime(s).strftime("%H:%M") for s in available_slots(self.day, 60)]
        self.assertIn("10:00", times)


class AppointmentValidationTests(SalonTestBase):
    def test_overlap_is_rejected(self):
        Appointment.objects.create(customer=self.ana, service=self.tinte, start=at(self.day, 9))
        other = Appointment(customer=self.ana, service=self.corte, start=at(self.day, 10))
        with self.assertRaises(ValidationError):
            other.clean()

    def test_outside_hours_is_rejected(self):
        late = Appointment(customer=self.ana, service=self.corte, start=at(self.day, 19, 30))
        with self.assertRaises(ValidationError):
            late.clean()
        early = Appointment(customer=self.ana, service=self.corte, start=at(self.day, 7))
        with self.assertRaises(ValidationError):
            early.clean()

    def test_editing_same_appointment_does_not_conflict_with_itself(self):
        appt = Appointment.objects.create(customer=self.ana, service=self.corte, start=at(self.day, 10))
        appt.notes = "Cambio de nota"
        appt.clean()  # no debe lanzar error


class ApiTests(SalonTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_list_services_only_active(self):
        Service.objects.create(name="Oculto", duration_minutes=30, price=1000, is_active=False)
        res = self.client.get("/api/services/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual({s["name"] for s in res.json()}, {"Corte", "Tinte"})

    def test_availability_endpoint(self):
        res = self.client.get(f"/api/availability/?service={self.corte.id}&date={self.day}")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.json()["slots"]), 0)

    def test_availability_requires_valid_params(self):
        self.assertEqual(self.client.get("/api/availability/").status_code, 400)

    def test_booking_creates_customer_and_appointment(self):
        payload = {
            "name": "María", "phone": "3109998877", "service": self.corte.id,
            "start": at(self.day, 14).isoformat(),
        }
        res = self.client.post("/api/appointments/", payload, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertTrue(Customer.objects.filter(phone="3109998877").exists())
        self.assertEqual(Appointment.objects.count(), 1)

    def test_same_phone_reuses_customer(self):
        for hour in (9, 11):
            self.client.post("/api/appointments/", {
                "name": "Ana", "phone": "3001112233", "service": self.corte.id,
                "start": at(self.day, hour).isoformat(),
            }, format="json")
        self.assertEqual(Customer.objects.filter(phone="3001112233").count(), 1)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_double_booking_is_rejected(self):
        payload = {
            "name": "María", "phone": "3109998877", "service": self.corte.id,
            "start": at(self.day, 14).isoformat(),
        }
        self.assertEqual(self.client.post("/api/appointments/", payload, format="json").status_code, 201)
        payload.update(name="Laura", phone="3205554433", start=at(self.day, 14, 30).isoformat())
        res = self.client.post("/api/appointments/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_booking_outside_hours_is_rejected(self):
        res = self.client.post("/api/appointments/", {
            "name": "María", "phone": "3109998877", "service": self.corte.id,
            "start": at(self.day, 20).isoformat(),
        }, format="json")
        self.assertEqual(res.status_code, 400)

    def test_invalid_phone_is_rejected(self):
        res = self.client.post("/api/appointments/", {
            "name": "María", "phone": "abc", "service": self.corte.id,
            "start": at(self.day, 10).isoformat(),
        }, format="json")
        self.assertEqual(res.status_code, 400)


class BookingRulesTests(SalonTestBase):
    """Reglas nuevas: no pasado, solo horas de la cuadrícula, límite por teléfono."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def book(self, start, phone="3109998877", name="María"):
        return self.client.post("/api/appointments/", {
            "name": name, "phone": phone, "service": self.corte.id, "start": start.isoformat(),
        }, format="json")

    def test_past_booking_is_rejected(self):
        past_day = timezone.localdate() - timedelta(days=3)
        res = self.book(at(past_day, 10))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_off_grid_time_is_rejected(self):
        self.assertEqual(self.book(at(self.day, 10, 7)).status_code, 400)
        self.assertEqual(self.book(at(self.day, 10, 15)).status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_grid_times_are_accepted(self):
        self.assertEqual(self.book(at(self.day, 10, 0)).status_code, 201)
        self.assertEqual(self.book(at(self.day, 11, 30)).status_code, 201)

    def test_phone_cannot_exceed_open_booking_limit(self):
        limit = 2
        for hour in range(9, 9 + limit):
            self.assertEqual(self.book(at(self.day, hour)).status_code, 201)
        res = self.book(at(self.day, 15))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Appointment.objects.count(), limit)

    def test_other_phone_is_not_affected_by_the_limit(self):
        for hour in (9, 10):
            self.book(at(self.day, hour))
        self.assertEqual(self.book(at(self.day, 15), phone="3205554433").status_code, 201)

    def test_cancelled_bookings_do_not_count_toward_limit(self):
        for hour in (9, 10):
            self.book(at(self.day, hour))
        Appointment.objects.update(status=Appointment.Status.CANCELLED)
        self.assertEqual(self.book(at(self.day, 15)).status_code, 201)

    def test_every_offered_slot_is_bookable(self):
        """Coherencia: toda hora que ofrece /availability/ pasa la validación."""
        res = self.client.get(f"/api/availability/?service={self.corte.id}&date={self.day}")
        slots = res.json()["slots"]
        self.assertGreater(len(slots), 0)
        # Se toman horas separadas 60 min (2 pasos de 30) para que no se crucen entre sí.
        for i, slot in enumerate(slots[0:6:2]):
            r = self.client.post("/api/appointments/", {
                "name": "Ana", "phone": f"31000000{i:02d}", "service": self.corte.id, "start": slot,
            }, format="json")
            self.assertEqual(r.status_code, 201, r.content)


class AdminActionTests(SalonTestBase):
    def test_confirm_action_respects_validation(self):
        from django.contrib.admin.sites import site
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from .admin import AppointmentAdmin

        user = get_user_model().objects.create_superuser("admin", "a@a.com", "pw")
        appt = Appointment.objects.create(customer=self.ana, service=self.corte, start=at(self.day, 10))
        request = RequestFactory().post("/admin/")
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)

        model_admin = AppointmentAdmin(Appointment, site)
        model_admin.confirm(request, Appointment.objects.all())
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.CONFIRMED)
