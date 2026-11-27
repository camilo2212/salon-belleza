"""Avisos para la dueña cuando entra una reserva nueva."""

import logging

from django.conf import settings
from django.core.mail import send_mail

from .whatsapp import when_text, whatsapp_url

logger = logging.getLogger(__name__)


def _send(subject: str, body: str, appointment) -> None:
    """Envía un correo a SALON_NOTIFY_EMAILS. Si falla, solo se registra: la cita ya existe."""
    recipients = getattr(settings, "SALON_NOTIFY_EMAILS", [])
    if not recipients:
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=None,  # usa DEFAULT_FROM_EMAIL
            recipient_list=recipients,
        )
    except Exception:  # noqa: BLE001 - un correo caído no debe tumbar la reserva
        logger.exception("No se pudo enviar el aviso de la cita %s", appointment.pk)


def _details(appointment) -> str:
    customer, service = appointment.customer, appointment.service
    return (
        f"Clienta: {customer.name}\n"
        f"WhatsApp: {customer.phone}\n"
        f"Servicio: {service.name}\n"
        f"Cuándo: {when_text(appointment)}\n\n"
        f"Escríbele por WhatsApp: {whatsapp_url(customer.phone)}\n"
    )


def notify_new_booking(appointment) -> None:
    _send(
        f"Nueva reserva: {appointment.customer.name} - {appointment.service.name}",
        "Nueva reserva pendiente de confirmar.\n\n"
        + _details(appointment)
        + "Confírmala o cancélala desde el panel de administración.",
        appointment,
    )


def notify_cancellation(appointment) -> None:
    _send(
        f"Cita cancelada: {appointment.customer.name} - {appointment.service.name}",
        "La clienta canceló su cita desde la página. El horario quedó libre.\n\n"
        + _details(appointment),
        appointment,
    )
