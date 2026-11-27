"""Normalización de teléfonos.

Una misma persona puede escribir su número como 3001234567, +573001234567 o
57 300 123 4567. Todos se guardan como 3001234567 para que cuenten como una sola
clienta (y para que el límite de citas por teléfono no se pueda saltar).
"""

import re

from django.conf import settings

_SEPARATORS = re.compile(r"[\s\-().]")
_VALID = re.compile(r"^\+?\d{7,15}$")


def normalize_phone(raw: str) -> str:
    """Devuelve solo dígitos, sin '+' ni indicativo del país si el número es local.

    No valida: úsala junto con `is_valid_phone`.
    """
    digits = _SEPARATORS.sub("", str(raw)).lstrip("+")
    if digits.startswith("00"):
        digits = digits[2:]
    country = getattr(settings, "SALON_COUNTRY_CODE", "57")
    local_length = getattr(settings, "SALON_LOCAL_PHONE_LENGTH", 10)
    if digits.startswith(country) and len(digits) == len(country) + local_length:
        digits = digits[len(country):]
    return digits


def is_valid_phone(raw: str) -> bool:
    return bool(_VALID.match(_SEPARATORS.sub("", str(raw))))
