from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from .availability import is_on_slot_grid, is_slot_free, is_within_business_hours
from .models import Appointment, Customer, Product, Service
from .notifications import notify_new_booking
from .phone import is_valid_phone, normalize_phone


def clean_phone(value):
    """Valida y deja el teléfono siempre igual (3001234567), para que +57... y 300... coincidan."""
    if not is_valid_phone(value):
        raise serializers.ValidationError("Escribe un número válido, solo dígitos.")
    return normalize_phone(value)


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
        return clean_phone(value)

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
                appointment = Appointment.objects.create(
                    customer=customer, service=service, start=start, user=validated_data.get("user")
                )
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


# --- Cuentas de clientas -------------------------------------------------------
# El usuario de la clienta es su número (sin indicativo). Las administradoras NO usan
# esto: entran por /admin/ con su propio usuario.


def profile(user):
    return {"name": user.first_name, "phone": user.username}


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=25)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate_phone(self, value):
        return clean_phone(value)

    def validate(self, data):
        User = get_user_model()
        if User.objects.filter(username=data["phone"]).exists():
            raise serializers.ValidationError(
                {"phone": ["Ya hay una cuenta con ese número. Ingresa con tu contraseña."]}
            )
        try:
            validate_password(data["password"], User(username=data["phone"], first_name=data["name"]))
        except DjangoValidationError as err:
            raise serializers.ValidationError({"password": list(err.messages)})
        return data

    def create(self, validated_data):
        try:
            return get_user_model().objects.create_user(
                username=validated_data["phone"],
                password=validated_data["password"],
                first_name=validated_data["name"].strip(),
            )
        except IntegrityError:  # dos registros al mismo tiempo con el mismo número
            raise serializers.ValidationError(
                {"phone": ["Ya hay una cuenta con ese número. Ingresa con tu contraseña."]}
            )


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=25)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate(self, data):
        user = authenticate(
            request=self.context.get("request"),
            username=normalize_phone(data["phone"]),
            password=data["password"],
        )
        # Mismo mensaje en todos los casos. Las cuentas de administración no entran por aquí.
        if user is None or user.is_staff or user.is_superuser:
            raise serializers.ValidationError("Número o contraseña incorrectos.")
        data["user"] = user
        return data


class MyAppointmentSerializer(serializers.ModelSerializer):
    service = serializers.CharField(source="service.name")
    status_label = serializers.CharField(source="get_status_display")
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = ["id", "service", "start", "end", "status", "status_label", "can_cancel"]

    def get_can_cancel(self, obj):
        return obj.can_be_cancelled_by_client()
