// En desarrollo se deja vacío (usa el proxy de Vite). En producción se define
// VITE_API_URL con la dirección del backend, ej. https://mi-salon-api.onrender.com
const BASE = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  constructor(status, data) {
    super(String(status))
    this.status = status
    this.data = data
  }
}

// El token de la clienta se guarda en este navegador para que la sesión dure entre visitas.
const TOKEN_KEY = 'salon_token'
export const tokenStore = {
  get() {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token) {
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* navegador sin almacenamiento: la sesión dura hasta cerrar la página */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* nada que borrar */
    }
  },
}

// `auth: true` envía el token. Solo se envía donde hace falta: un token vencido
// no debe romper las pantallas públicas (servicios, horas libres).
async function request(path, { auth = false, headers, ...options } = {}) {
  const finalHeaders = { 'Content-Type': 'application/json', ...headers }
  const token = auth ? tokenStore.get() : null
  if (token) finalHeaders.Authorization = `Token ${token}`
  let res
  try {
    res = await fetch(`${BASE}${path}`, { headers: finalHeaders, ...options })
  } catch {
    throw new ApiError('network', null)
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

const post = (path, body, auth = false) =>
  request(path, { method: 'POST', auth, body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  services: (signal) => request('/api/services/', { signal }),
  products: (signal) => request('/api/products/', { signal }),
  availability: (serviceId, day, signal) =>
    request(`/api/availability/?service=${serviceId}&date=${day}`, { signal }),
  // Con sesión iniciada la API usa los datos de la cuenta; sin sesión, nombre y WhatsApp.
  book: (body, auth = false) => post('/api/appointments/', body, auth),

  // Cuentas de clientas (las administradoras entran por /admin/, no por aquí)
  register: (body) => post('/api/auth/register/', body),
  login: (body) => post('/api/auth/login/', body),
  logout: () => post('/api/auth/logout/', undefined, true),
  me: (signal) => request('/api/auth/me/', { auth: true, signal }),
  myAppointments: (signal) => request('/api/my/appointments/', { auth: true, signal }),
  cancelAppointment: (id) => post(`/api/my/appointments/${id}/cancel/`, undefined, true),
}

function collect(data) {
  if (typeof data === 'string') return [data]
  if (Array.isArray(data)) return data.flatMap(collect)
  if (data && typeof data === 'object') return Object.values(data).flatMap(collect)
  return []
}

// Convierte cualquier error de la API en un mensaje que la clienta pueda entender y usar.
export function errorMessage(err) {
  if (err.status === 'network') {
    return 'No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo.'
  }
  if (err.status === 401) {
    return 'Tu sesión venció. Ingresa de nuevo.'
  }
  if (err.status === 404) {
    return 'No encontramos esa cita. Recarga la página.'
  }
  if (err.status === 429) {
    return 'Hiciste muchos intentos seguidos. Espera un minuto e inténtalo otra vez.'
  }
  if (err.status === 400) {
    const messages = collect(err.data)
    if (messages.length) return messages.join(' ')
  }
  return 'Algo salió mal de nuestro lado. Inténtalo de nuevo en unos minutos.'
}

// Errores de un formulario de cuenta, separados por campo para mostrarlos junto a cada casilla.
export function fieldErrors(err) {
  if (err.status !== 400 || !err.data || typeof err.data !== 'object' || Array.isArray(err.data)) {
    return { form: errorMessage(err) }
  }
  const out = {}
  for (const key of ['name', 'phone', 'password']) {
    if (err.data[key]) out[key] = collect(err.data[key]).join(' ')
  }
  const rest = collect(err.data.non_field_errors ?? err.data.detail ?? [])
  if (rest.length) out.form = rest.join(' ')
  return Object.keys(out).length ? out : { form: errorMessage(err) }
}
