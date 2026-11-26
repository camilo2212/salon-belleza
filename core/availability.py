"""Cálculo de horarios disponibles.

El salón tiene una sola agenda (la dueña atiende sola): una cita ocupa un bloque
de tiempo y no puede cruzarse con otra.
"""

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.utils import timezone

from .models import Appointment

# Horario de atención configurable desde settings.py
OPEN_TIME = time(*getattr(settings, "SALON_OPEN", (8, 0)))
CLOSE_TIME = time(*getattr(settings, "SALON_CLOSE", (20, 0)))
SLOT_STEP_MINUTES = getattr(settings, "SALON_SLOT_STEP_MINUTES", 30)
# Días cerrados: 0 = lunes ... 6 = domingo
CLOSED_WEEKDAYS = getattr(settings, "SALON_CLOSED_WEEKDAYS", [])


def _aware(day: date, t: time) -> datetime:
    return timezone.make_aware(datetime.combine(day, t))


def is_within_business_hours(start: datetime, end: datetime) -> bool:
    start_l, end_l = timezone.localtime(start), timezone.localtime(end)
    if start_l.date() != end_l.date():
        return False
    if start_l.weekday() in CLOSED_WEEKDAYS:
        return False
    day = start_l.date()
    return _aware(day, OPEN_TIME) <= start_l and end_l <= _aware(day, CLOSE_TIME)


def is_slot_free(start: datetime, end: datetime, exclude_id=None) -> bool:
    """True si no hay ninguna cita activa que se cruce con [start, end)."""
    overlapping = Appointment.objects.filter(
        status__in=Appointment.BLOCKING_STATUSES, start__lt=end, end__gt=start
    )
    if exclude_id:
        overlapping = overlapping.exclude(pk=exclude_id)
    return not overlapping.exists()


def available_slots(day: date, duration_minutes: int) -> list[datetime]:
    """Horas de inicio disponibles para un servicio de `duration_minutes` en `day`."""
    if day.weekday() in CLOSED_WEEKDAYS:
        return []

    open_dt, close_dt = _aware(day, OPEN_TIME), _aware(day, CLOSE_TIME)
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=SLOT_STEP_MINUTES)

    busy = list(
        Appointment.objects.filter(
            status__in=Appointment.BLOCKING_STATUSES, start__lt=close_dt, end__gt=open_dt
        ).values_list("start", "end")
    )

    now = timezone.now()
    slots = []
    current = open_dt
    while current + duration <= close_dt:
        end = current + duration
        is_future = current > now
        is_free = all(not (b_start < end and b_end > current) for b_start, b_end in busy)
        if is_future and is_free:
            slots.append(current)
        current += step
    return slots
