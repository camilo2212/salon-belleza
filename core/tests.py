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


class PhoneNormalizationTests(SalonTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def book(self, start, phone, name="María"):
        return self.client.post("/api/appointments/", {
            "name": name, "phone": phone, "service": self.corte.id, "start": start.isoformat(),
        }, format="json")

    def test_normalize_phone_variants(self):
        from .phone import normalize_phone

        for raw in ("3109998877", "+573109998877", "57 310 999 8877", "310-999-8877", "00573109998877"):
            self.assertEqual(normalize_phone(raw), "3109998877", raw)
        self.assertEqual(normalize_phone("+14155550123"), "14155550123")  # extranjero: se respeta

    def test_different_formats_are_the_same_customer(self):
        self.assertEqual(self.book(at(self.day, 9), "3109998877").status_code, 201)
        self.assertEqual(self.book(at(self.day, 11), "+57 310 999 8877").status_code, 201)
        self.assertEqual(Customer.objects.filter(phone="3109998877").count(), 1)

    def test_formats_cannot_bypass_the_booking_limit(self):
        self.book(at(self.day, 9), "3109998877")
        self.book(at(self.day, 10), "+573109998877")
        res = self.book(at(self.day, 15), "573109998877")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_customer_clean_normalizes_before_unique_check(self):
        Customer.objects.create(name="María", phone="3109998877")
        dup = Customer(name="Otra", phone="+57 310 999 8877")
        with self.assertRaises(ValidationError):
            dup.full_clean()

    def test_returning_customer_gets_latest_name(self):
        self.book(at(self.day, 9), "3109998877", name="Mari")
        self.book(at(self.day, 11), "3109998877", name="María José")
        self.assertEqual(Customer.objects.get(phone="3109998877").name, "María José")


class RaceConditionTests(SalonTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_integrity_error_becomes_friendly_400(self):
        """Si la base de datos rechaza el cruce, la clienta ve un mensaje claro (no un error 500)."""
        from unittest import mock

        from django.db import IntegrityError

        with mock.patch("core.serializers.Appointment.objects.create", side_effect=IntegrityError):
            res = self.client.post("/api/appointments/", {
                "name": "María", "phone": "3109998877", "service": self.corte.id,
                "start": at(self.day, 14).isoformat(),
            }, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("ya fue tomado", str(res.json()))

    def test_database_blocks_overlap_on_postgresql(self):
        from django.db import IntegrityError, connection, transaction

        if connection.vendor != "postgresql":
            self.skipTest("La restricción anti-cruce solo existe en PostgreSQL.")
        Appointment.objects.create(customer=self.ana, service=self.corte, start=at(self.day, 10))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.create(customer=self.ana, service=self.corte, start=at(self.day, 10, 30))
        # Una cita cancelada no ocupa agenda, así que sí puede coexistir.
        Appointment.objects.create(
            customer=self.ana, service=self.corte, start=at(self.day, 10, 30),
            status=Appointment.Status.CANCELLED,
        )


class NotificationTests(SalonTestBase):
    def test_new_booking_sends_email_to_owner(self):
        from django.core import mail
        from django.test import override_settings

        client = APIClient()
        with override_settings(SALON_NOTIFY_EMAILS=["duena@example.com"]):
            with self.captureOnCommitCallbacks(execute=True):
                res = client.post("/api/appointments/", {
                    "name": "María", "phone": "3109998877", "service": self.corte.id,
                    "start": at(self.day, 14).isoformat(),
                }, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["duena@example.com"])
        self.assertIn("María", mail.outbox[0].body)
        self.assertIn("https://wa.me/573109998877", mail.outbox[0].body)

    def test_no_email_when_not_configured(self):
        from django.core import mail

        with self.captureOnCommitCallbacks(execute=True):
            APIClient().post("/api/appointments/", {
                "name": "María", "phone": "3109998877", "service": self.corte.id,
                "start": at(self.day, 14).isoformat(),
            }, format="json")
        self.assertEqual(len(mail.outbox), 0)

    def test_email_failure_does_not_break_the_booking(self):
        from unittest import mock

        from django.test import override_settings

        with override_settings(SALON_NOTIFY_EMAILS=["duena@example.com"]), \
                mock.patch("core.notifications.send_mail", side_effect=OSError("smtp caído")):
            with self.assertLogs("core.notifications", "ERROR"), \
                    self.captureOnCommitCallbacks(execute=True):
                res = APIClient().post("/api/appointments/", {
                    "name": "María", "phone": "3109998877", "service": self.corte.id,
                    "start": at(self.day, 14).isoformat(),
                }, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Appointment.objects.count(), 1)


class AdminAgendaTests(SalonTestBase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_superuser("admin", "a@a.com", "pw")
        self.client.login(username="admin", password="pw")
        today = timezone.localdate()
        self.today_appt = Appointment.objects.create(
            customer=self.ana, service=self.corte, start=at(today + timedelta(days=1), 10))
        self.far_appt = Appointment.objects.create(
            customer=self.ana, service=self.corte, start=at(today + timedelta(days=20), 10))
        self.past_appt = Appointment.objects.create(
            customer=self.ana, service=self.corte, start=at(today - timedelta(days=5), 10),
            status=Appointment.Status.COMPLETED)

    def ids(self, query):
        res = self.client.get(f"/admin/core/appointment/?{query}")
        self.assertEqual(res.status_code, 200)
        return {a.pk for a in res.context["cl"].result_list}

    def test_opening_the_list_defaults_to_upcoming(self):
        res = self.client.get("/admin/core/appointment/")
        self.assertRedirects(res, "/admin/core/appointment/?when=upcoming")

    def test_filters(self):
        self.assertEqual(self.ids("when=upcoming"), {self.today_appt.pk, self.far_appt.pk})
        self.assertEqual(self.ids("when=tomorrow"), {self.today_appt.pk})
        self.assertEqual(self.ids("when=week"), {self.today_appt.pk})
        self.assertEqual(self.ids("when=past"), {self.past_appt.pk})
        self.assertEqual(self.ids("when=all"), {self.today_appt.pk, self.far_appt.pk, self.past_appt.pk})

    def test_whatsapp_link_has_prefilled_message(self):
        res = self.client.get("/admin/core/appointment/?when=all")
        html = res.content.decode()
        self.assertIn("https://wa.me/573001112233?text=Hola%20Ana", html)
        self.assertIn("Confirmar por WhatsApp", html)

    def test_complete_and_no_show_actions(self):
        from django.contrib.admin.sites import site
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from .admin import AppointmentAdmin

        request = RequestFactory().post("/admin/")
        request.user = get_user_model().objects.get(username="admin")
        request.session = {}
        request._messages = FallbackStorage(request)
        model_admin = AppointmentAdmin(Appointment, site)

        model_admin.mark_no_show(request, Appointment.objects.filter(pk=self.today_appt.pk))
        model_admin.mark_completed(request, Appointment.objects.filter(pk=self.far_appt.pk))
        self.today_appt.refresh_from_db()
        self.far_appt.refresh_from_db()
        self.assertEqual(self.today_appt.status, Appointment.Status.NO_SHOW)
        self.assertEqual(self.far_appt.status, Appointment.Status.COMPLETED)


class OwnerPanelTests(SalonTestBase):
    """El usuario de la dueña (grupo "Dueña") maneja lo del salón y nada más."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        self.mama = get_user_model().objects.create_user("mama", password="pw12345!", is_staff=True)
        self.mama.groups.add(Group.objects.get(name="Dueña"))
        self.client.login(username="mama", password="pw12345!")

    def test_group_exists_after_migrate(self):
        from django.contrib.auth.models import Group

        group = Group.objects.get(name="Dueña")
        self.assertEqual(group.permissions.count(), 15)

    def test_owner_can_open_her_sections(self):
        for section in ("service", "product", "customer", "appointment"):
            res = self.client.get(f"/admin/core/{section}/", follow=True)
            self.assertEqual(res.status_code, 200, section)

    def test_owner_cannot_touch_users_or_groups(self):
        for url in ("/admin/auth/user/", "/admin/auth/group/", "/admin/auth/user/add/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_owner_can_change_a_price(self):
        res = self.client.post(f"/admin/core/service/{self.corte.pk}/change/", {
            "name": "Corte", "description": "", "duration_minutes": 60,
            "price": 35000, "is_active": "on",
        })
        self.assertEqual(res.status_code, 302)
        self.corte.refresh_from_db()
        self.assertEqual(self.corte.price, 35000)

    def test_owner_can_add_a_product(self):
        from .models import Product

        res = self.client.post("/admin/core/product/add/", {
            "name": "Shampoo", "description": "", "price": 28000, "stock": 5, "is_active": "on",
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Product.objects.filter(name="Shampoo", stock=5).exists())

    def test_stock_filter(self):
        from .models import Product

        Product.objects.create(name="Agotado", price=1000, stock=0)
        Product.objects.create(name="Pocas", price=1000, stock=2)
        Product.objects.create(name="Bien", price=1000, stock=50)

        def names(q):
            res = self.client.get(f"/admin/core/product/?{q}")
            return {p.name for p in res.context["cl"].result_list}

        self.assertEqual(names("stock=out"), {"Agotado"})
        self.assertEqual(names("stock=low"), {"Agotado", "Pocas"})

    def test_customer_list_shows_history_summary(self):
        today = timezone.localdate()
        Appointment.objects.create(customer=self.ana, service=self.corte, start=at(today - timedelta(days=9), 10),
                                   status=Appointment.Status.COMPLETED)
        Appointment.objects.create(customer=self.ana, service=self.corte, start=at(today - timedelta(days=5), 10),
                                   status=Appointment.Status.NO_SHOW)
        res = self.client.get("/admin/core/customer/")
        ana = next(c for c in res.context["cl"].result_list if c.pk == self.ana.pk)
        self.assertEqual((ana._visits, ana._no_shows), (1, 1))
        # Ficha de la clienta: muestra su historial sin errores
        self.assertEqual(self.client.get(f"/admin/core/customer/{self.ana.pk}/change/").status_code, 200)
