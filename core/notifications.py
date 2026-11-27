"""Avisos para la dueña cuando entra una reserva nueva."""

import logging

from django.conf import settings
from django.core.mail import send_mail

from .whatsapp import when_text, whatsapp_url

logger = logging.getLogger(__name__)


def notify_new_booking(appointment) -> None:
    """Envía un correo a SALON_NOTIFY_EMAILS. Si falla, solo se registra: la reserva ya existe."""
    recipients = getattr(settings, "SALON_NOTIFY_EMAILS", [])
    if not recipients:
        return
    customer, service = appointment.customer, appointment.service
    body = (
        f"Nueva reserva pendiente de confirmar.\n\n"
        f"Clienta: {customer.name}\n"
        f"WhatsApp: {customer.phone}\n"
        f"Servicio: {service.name}\n"
        f"Cuándo: {when_text(appointment)}\n\n"
        f"Escríbele por WhatsApp: {whatsapp_url(customer.phone)}\n"
        "Confírmala o cancélala desde el panel de administración."
    )
    try:
        send_mail(
            subject=f"Nueva reserva: {customer.name} - {service.name}",
            message=body,
            from_email=None,  # usa DEFAULT_FROM_EMAIL
            recipient_list=recipients,
        )
    except Exception:  # noqa: BLE001 - un correo caído no debe tumbar la reserva
        logger.exception("No se pudo enviar el aviso de la reserva %s", appointment.pk)
