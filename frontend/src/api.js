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

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new ApiError('network', null)
  }
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

export const api = {
  services: (signal) => request('/api/services/', { signal }),
  products: (signal) => request('/api/products/', { signal }),
  availability: (serviceId, day, signal) =>
    request(`/api/availability/?service=${serviceId}&date=${day}`, { signal }),
  book: (body) => request('/api/appointments/', { method: 'POST', body: JSON.stringify(body) }),
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
  if (err.status === 429) {
    return 'Hiciste muchos intentos seguidos. Espera un minuto e inténtalo otra vez.'
  }
  if (err.status === 400) {
    const messages = collect(err.data)
    if (messages.length) return messages.join(' ')
  }
  return 'Algo salió mal de nuestro lado. Inténtalo de nuevo en unos minutos.'
}
