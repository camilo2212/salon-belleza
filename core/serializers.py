from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from .availability import is_on_slot_grid, is_slot_free, is_within_business_hours
from .models import Appointment, Customer, Product, Service
from .notifications import notify_new_booking
from .phone import is_valid_phone, normalize_phone


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "description", "duration_minutes", "price"]


class ProductSerializer(serializers.ModelSerializer):
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "image", "in_stock"]


class BookingSerializer(serializers.Serializer):
    """Reserva pública: la clienta solo deja nombre, WhatsApp, servicio y hora."""

    name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=25)
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    start = serializers.DateTimeField()

    def validate_phone(self, value):
        if not is_valid_phone(value):
            raise serializers.ValidationError("Escribe un número válido, solo dígitos.")
        # Se guarda siempre igual (3001234567) para que +57... y 300... sean la misma clienta.
        return normalize_phone(value)

    def validate(self, data):
        start = data["start"]
        end = start + timedelta(minutes=data["service"].duration_minutes)

        if start <= timezone.now():
            raise serializers.ValidationError("No se puede reservar en una fecha u hora que ya pasó.")
        if not is_within_business_hours(start, end):
            raise serializers.ValidationError("Ese horario está fuera de la atención del salón.")
        if not is_on_slot_grid(start):
            raise serializers.ValidationError("Elige una de las horas disponibles que ofrece el salón.")

        # Evita que una misma persona llene la agenda con reservas sin atender.
        max_open = getattr(settings, "SALON_MAX_OPEN_BOOKINGS_PER_PHONE", 2)
        open_bookings = Appointment.objects.filter(
            customer__phone=data["phone"],
            status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
            start__gt=timezone.now(),
        ).count()
        if open_bookings >= max_open:
            raise serializers.ValidationError(
                f"Ya tienes {open_bookings} citas pendientes. Escríbenos por WhatsApp para agendar otra."
            )
        return data

    def create(self, validated_data):
        service, start = validated_data["service"], validated_data["start"]
        end = start + timedelta(minutes=service.duration_minutes)

        taken = serializers.ValidationError("Ese horario ya fue tomado, elige otro.")
        try:
            with transaction.atomic():
                if not is_slot_free(start, end):
                    raise taken
                customer, created = Customer.objects.get_or_create(
                    phone=validated_data["phone"], defaults={"name": validated_data["name"]}
                )
                if not created and customer.name != validated_data["name"]:
                    customer.name = validated_data["name"]
                    customer.save(update_fields=["name"])
                appointment = Appointment.objects.create(customer=customer, service=service, start=start)
        except IntegrityError:
            # En PostgreSQL la base de datos rechaza el cruce aunque dos personas
            # reserven a la vez (restricción de la migración 0002).
            raise taken
        transaction.on_commit(lambda: notify_new_booking(appointment))
        return appointment


class AppointmentConfirmationSerializer(serializers.ModelSerializer):
    service = serializers.CharField(source="service.name")

    class Meta:
        model = Appointment
        fields = ["id", "service", "start", "end", "status"]
