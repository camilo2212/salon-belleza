// Formatos de precio, duración, fechas y horas. Todo se muestra en hora de Colombia.
const TZ = 'America/Bogota'

export const money = (value) =>
  new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(Number(value))

export function duration(minutes) {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (!h) return `${m} min`
  if (!m) return `${h} h`
  return `${h} h ${m} min`
}

// --- Fechas como texto AAAA-MM-DD (así las entiende la API) -------------------
export const todayISO = () => new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(new Date())

export function addDays(iso, n) {
  const d = new Date(`${iso}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

export const nextDays = (n) => Array.from({ length: n }, (_, i) => addDays(todayISO(), i))

const noDot = (s) => s.replace('.', '')
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)
const atNoon = (iso) => new Date(`${iso}T12:00:00Z`)

export function dayParts(iso) {
  const d = atNoon(iso)
  return {
    weekday: noDot(new Intl.DateTimeFormat('es-CO', { weekday: 'short', timeZone: 'UTC' }).format(d)),
    num: d.getUTCDate(),
    month: noDot(new Intl.DateTimeFormat('es-CO', { month: 'short', timeZone: 'UTC' }).format(d)),
  }
}

export function dayLabel(iso) {
  const today = todayISO()
  if (iso === today) return 'Hoy'
  if (iso === addDays(today, 1)) return 'Mañana'
  const { weekday, num, month } = dayParts(iso)
  return `${cap(weekday)} ${num} ${month}`
}

const longFmt = (tz) =>
  new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'long', timeZone: tz })

// "jueves 3 de diciembre" a partir de AAAA-MM-DD
export const longDay = (iso) => longFmt('UTC').format(atNoon(iso)).replace(',', '')
// ... y a partir de un instante completo devuelto por la API
export const longDayAt = (instant) => longFmt(TZ).format(new Date(instant)).replace(',', '')

// --- Horas ---------------------------------------------------------------------
const timeFmt = new Intl.DateTimeFormat('es-CO', {
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
  timeZone: TZ,
})
export const timeLabel = (instant) =>
  timeFmt.format(new Date(instant)).replace(/\s*([ap])\.?\s?m\.?/i, ' $1m').toLowerCase()

const keyFmt = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: TZ,
})
// "08:30" (hora de Colombia) para ubicar cada hora en la agenda
export const timeKey = (instant) => keyFmt.format(new Date(instant))

export const addMinutes = (instant, minutes) =>
  new Date(new Date(instant).getTime() + minutes * 60000).toISOString()

export function hourLabel(h) {
  if (h === 12) return '12 pm'
  return h < 12 ? `${h} am` : `${h - 12} pm`
}

export function chipLabel(h, mm) {
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}:${mm}`
}
