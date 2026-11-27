"""Enlaces de WhatsApp con el mensaje ya escrito, para que la dueña solo pulse enviar."""

from urllib.parse import quote

from django.conf import settings
from django.utils import timezone
from django.utils.formats import date_format


def whatsapp_url(phone: str, text: str = "") -> str:
    country = getattr(settings, "SALON_COUNTRY_CODE", "57")
    local_length = getattr(settings, "SALON_LOCAL_PHONE_LENGTH", 10)
    number = phone if len(phone) > local_length else f"{country}{phone}"
    url = f"https://wa.me/{number}"
    return f"{url}?text={quote(text)}" if text else url


def when_text(appointment) -> str:
    """Ej.: 'jueves 3 de diciembre a las 3:00 p. m.'"""
    local = timezone.localtime(appointment.start)
    return f"{date_format(local, r'l j \d\e F')} a las {date_format(local, 'g:i a')}"


def confirmation_message(appointment) -> str:
    salon = getattr(settings, "SALON_NAME", "el salón")
    return (
        f"Hola {appointment.customer.name}, te escribimos de {salon}. "
        f"Tu cita de {appointment.service.name} el {when_text(appointment)} está confirmada. "
        "¡Te esperamos!"
    )
