// Datos del salón. Cámbialos aquí y se actualizan en toda la página.
export const SALON = {
  name: 'Salón de Belleza', // TODO: nombre real del salón
  tagline: 'Reserva tu hora en un minuto, sin crear cuenta.',
  whatsapp: '', // código de país + número, ej. '573001234567'. Vacío = se oculta el botón
  address: '', // ej. 'Calle 10 #5-20, barrio Centro'. Vacío = se oculta
  hours: 'De 8:00 am a 8:00 pm',
  // Deben coincidir con SALON_OPEN y SALON_CLOSE del backend (config/settings.py)
  openHour: 8,
  closeHour: 20,
}

// Panel de administración (tú y la dueña). Es un acceso aparte del de las clientas.
export const ADMIN_URL = `${import.meta.env.VITE_API_URL ?? ''}/admin/`
