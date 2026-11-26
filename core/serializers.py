from datetime import timedelta

from django.db import transaction
from rest_framework import serializers

from .availability import is_slot_free, is_within_business_hours
from .models import Appointment, Customer, Product, Service


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
    phone = serializers.RegexField(
        r"^\+?\d{7,15}$", error_messages={"invalid": "Escribe un número válido, solo dígitos."}
    )
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    start = serializers.DateTimeField()

    def validate(self, data):
        end = data["start"] + timedelta(minutes=data["service"].duration_minutes)
        if not is_within_business_hours(data["start"], end):
            raise serializers.ValidationError("Ese horario está fuera de la atención del salón.")
        return data

    def create(self, validated_data):
        service, start = validated_data["service"], validated_data["start"]
        end = start + timedelta(minutes=service.duration_minutes)

        # transaction + select_for_update reduce la posibilidad de que dos clientas
        # reserven el mismo horario al mismo tiempo (aplica en PostgreSQL).
        with transaction.atomic():
            list(Appointment.objects.select_for_update().filter(start__date=start.date()))
            if not is_slot_free(start, end):
                raise serializers.ValidationError("Ese horario ya fue tomado, elige otro.")
            customer, _ = Customer.objects.get_or_create(
                phone=validated_data["phone"], defaults={"name": validated_data["name"]}
            )
            return Appointment.objects.create(customer=customer, service=service, start=start)


class AppointmentConfirmationSerializer(serializers.ModelSerializer):
    service = serializers.CharField(source="service.name")

    class Meta:
        model = Appointment
        fields = ["id", "service", "start", "end", "status"]
