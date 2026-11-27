from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .phone import is_valid_phone, normalize_phone


class Service(models.Model):
    """Servicio que ofrece el salón (corte, tinte, uñas...)."""

    name = models.CharField("nombre", max_length=100)
    description = models.TextField("descripción", blank=True)
    duration_minutes = models.PositiveIntegerField("duración (minutos)", default=60)
    price = models.DecimalField("precio", max_digits=10, decimal_places=0)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.duration_minutes} min)"


class Product(models.Model):
    """Producto que vende el salón. Por ahora solo catálogo, sin compra en línea."""

    name = models.CharField("nombre", max_length=100)
    description = models.TextField("descripción", blank=True)
    price = models.DecimalField("precio", max_digits=10, decimal_places=0)
    stock = models.PositiveIntegerField("existencias", default=0)
    image = models.ImageField("foto", upload_to="products/", blank=True)
    is_active = models.BooleanField("visible en catálogo", default=True)

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0


class Customer(models.Model):
    """Clienta. Se crea automáticamente la primera vez que reserva."""

    name = models.CharField("nombre", max_length=100)
    phone = models.CharField("WhatsApp / teléfono", max_length=20, unique=True)
    notes = models.TextField("notas", blank=True)
    created_at = models.DateTimeField("registrada", auto_now_add=True)

    class Meta:
        verbose_name = "clienta"
        verbose_name_plural = "clientas"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.phone}"

    def clean(self):
        # Corre antes de la validación de "único", así +57300... y 300... no se duplican.
        if self.phone:
            if not is_valid_phone(self.phone):
                raise ValidationError({"phone": "Escribe un número válido, solo dígitos."})
            self.phone = normalize_phone(self.phone)

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        CONFIRMED = "confirmed", "Confirmada"
        COMPLETED = "completed", "Realizada"
        CANCELLED = "cancelled", "Cancelada"
        NO_SHOW = "no_show", "No asistió"

    # Estados que ocupan la agenda (una cita cancelada libera el horario).
    BLOCKING_STATUSES = [Status.PENDING, Status.CONFIRMED, Status.COMPLETED]

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="appointments", verbose_name="clienta"
    )
    service = models.ForeignKey(
        Service, on_delete=models.PROTECT, related_name="appointments", verbose_name="servicio"
    )
    # Cuenta de la clienta si reservó con sesión iniciada (así ve y cancela sus citas).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
        on_delete=models.SET_NULL, related_name="appointments", verbose_name="cuenta",
    )
    start = models.DateTimeField("inicio")
    end = models.DateTimeField("fin", editable=False)
    status = models.CharField(
        "estado", max_length=12, choices=Status.choices, default=Status.PENDING
    )
    notes = models.TextField("notas", blank=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        verbose_name = "cita"
        verbose_name_plural = "citas"
        ordering = ["start"]

    def __str__(self):
        local = timezone.localtime(self.start)
        return f"{self.customer.name} - {self.service.name} - {local:%d/%m %H:%M}"

    def can_be_cancelled_by_client(self):
        """La clienta puede cancelar sola si la cita sigue activa y faltan al menos N horas."""
        if self.status not in (self.Status.PENDING, self.Status.CONFIRMED):
            return False
        min_hours = getattr(settings, "SALON_CANCEL_MIN_HOURS", 2)
        return self.start - timezone.now() >= timedelta(hours=min_hours)

    def clean(self):
        # Se importa aquí para evitar importaciones circulares.
        from .availability import is_slot_free, is_within_business_hours

        if not self.service_id or not self.start:
            return

        end = self.start + timedelta(minutes=self.service.duration_minutes)

        if self.status in self.BLOCKING_STATUSES:
            if not is_within_business_hours(self.start, end):
                raise ValidationError("La cita queda fuera del horario de atención (8 am a 8 pm).")
            if not is_slot_free(self.start, end, exclude_id=self.pk):
                raise ValidationError("Ya hay otra cita en ese horario.")

    def save(self, *args, **kwargs):
        self.end = self.start + timedelta(minutes=self.service.duration_minutes)
        super().save(*args, **kwargs)
