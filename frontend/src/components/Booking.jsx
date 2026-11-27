import { useEffect, useMemo, useRef, useState } from 'react'
import { api, errorMessage } from '../api'
import { useAuth } from '../auth'
import { SALON } from '../config'
import {
  addMinutes,
  chipLabel,
  dayParts,
  duration,
  hourLabel,
  longDay,
  longDayAt,
  money,
  nextDays,
  timeKey,
  timeLabel,
} from '../format'

const DAYS = nextDays(14)
const HOURS = Array.from({ length: SALON.closeHour - SALON.openHour }, (_, i) => SALON.openHour + i)
const pad = (n) => String(n).padStart(2, '0')

export default function Booking({ services, intent, onBooked, onLogin }) {
  const { user, expire } = useAuth()
  const [serviceId, setServiceId] = useState(null)
  const [day, setDay] = useState(DAYS[0])
  const [slots, setSlots] = useState(null) // null = cargando
  const [slotsError, setSlotsError] = useState('')
  const [reload, setReload] = useState(0)
  const [picked, setPicked] = useState(null)
  const [form, setForm] = useState({ name: '', phone: '' })
  const [errors, setErrors] = useState({})
  const [notice, setNotice] = useState('')
  const [sending, setSending] = useState(false)
  const [done, setDone] = useState(null)
  const pendingSlot = useRef(null)
  const formRef = useRef(null)

  const service = services.find((s) => s.id === serviceId) ?? null

  // La clienta eligió un servicio o una hora desde el inicio o desde la lista de servicios.
  useEffect(() => {
    if (!intent) return
    pendingSlot.current = intent.slot ?? null
    setDone(null)
    setNotice('')
    if (intent.serviceId != null) setServiceId(intent.serviceId)
    if (intent.day) setDay(intent.day)
    setReload((n) => n + 1)
  }, [intent])

  // Pide las horas libres cada vez que cambia el servicio o el día.
  useEffect(() => {
    if (serviceId == null) {
      setSlots(null)
      return
    }
    const ctrl = new AbortController()
    setSlots(null)
    setSlotsError('')
    setPicked(null)
    api
      .availability(serviceId, day, ctrl.signal)
      .then((data) => {
        setSlots(data.slots)
        if (pendingSlot.current && data.slots.includes(pendingSlot.current)) {
          setPicked(pendingSlot.current)
        }
        pendingSlot.current = null
      })
      .catch((err) => !ctrl.signal.aborted && setSlotsError(errorMessage(err)))
    return () => ctrl.abort()
  }, [serviceId, day, reload])

  // En celular el formulario queda debajo de la agenda: lo traemos a la vista.
  useEffect(() => {
    if (picked && window.matchMedia('(max-width: 899px)').matches) {
      formRef.current?.scrollIntoView({ block: 'center' })
    }
  }, [picked])

  const available = useMemo(
    () => new Map((slots ?? []).map((iso) => [timeKey(iso), iso])),
    [slots],
  )

  function chooseService(id) {
    setServiceId(id)
    setNotice('')
  }

  function chooseDay(d) {
    setDay(d)
    setNotice('')
  }

  function chooseSlot(iso) {
    setPicked(iso)
    setNotice('')
  }

  async function submit(e) {
    e.preventDefault()
    // Con sesión iniciada no se piden datos: la API usa los de la cuenta.
    const name = user ? user.name : form.name.trim()
    const phone = form.phone.replace(/[\s\-().]/g, '')
    if (!user) {
      const found = {}
      if (name.length < 2) found.name = 'Escribe tu nombre.'
      if (!/^\+?\d{7,15}$/.test(phone)) {
        found.phone = 'Escribe tu número de WhatsApp solo con dígitos. Ejemplo: 3001234567'
      }
      setErrors(found)
      if (Object.keys(found).length) return
    }

    setSending(true)
    setNotice('')
    try {
      const body = user
        ? { service: service.id, start: picked }
        : { name, phone, service: service.id, start: picked }
      const res = await api.book(body, Boolean(user))
      setDone({ ...res, name })
      onBooked?.()
    } catch (err) {
      if (user && err.status === 401) {
        expire()
        setNotice('Tu sesión venció. Ingresa de nuevo, o reserva con tu nombre y WhatsApp.')
        return
      }
      setNotice(errorMessage(err))
      // Un error que no es de un campo significa que la hora ya no está libre: actualizamos la agenda.
      if (err.status === 400 && Array.isArray(err.data)) setReload((n) => n + 1)
    } finally {
      setSending(false)
    }
  }

  function startOver() {
    setDone(null)
    setForm({ name: '', phone: '' })
    setPicked(null)
    setReload((n) => n + 1)
  }

  if (done) {
    return (
      <section id="reservar" className="section section-tint">
        <div className="wrap">
          <div className="done" role="status">
            <h2>Cita registrada</h2>
            <p>
              {done.name}, reservaste <strong>{done.service}</strong> para el{' '}
              <strong>{longDayAt(done.start)}</strong> de{' '}
              <strong>
                {timeLabel(done.start)} a {timeLabel(done.end)}
              </strong>
              .
            </p>
            <p className="muted">El salón confirmará tu cita contigo antes de la fecha.</p>
            {user && (
              <p className="muted">
                La ves, o la cancelas, en <a href="#mis-citas">Mis citas</a>.
              </p>
            )}
            <button type="button" className="btn btn-line" onClick={startOver}>
              Reservar otra cita
            </button>
          </div>
        </div>
      </section>
    )
  }

  const noSlotsToday = slots !== null && slots.length === 0

  return (
    <section id="reservar" className="section section-tint">
      <div className="wrap">
        <h2>Reservar cita</h2>
        <p className="lede">
          {user
            ? 'Reservas con tu cuenta, sin escribir tus datos otra vez.'
            : 'Sin crear cuenta. Solo necesitamos tu nombre y tu WhatsApp.'}
        </p>
        {!user && onLogin && (
          <p className="muted login-hint">
            ¿Ya tienes cuenta?{' '}
            <button type="button" className="btn-text" onClick={onLogin}>
              Ingresa
            </button>{' '}
            para ver y cancelar tus citas.
          </p>
        )}

        <div className="booking">
          <fieldset className="step area-service">
            <legend>
              <span className="step-n">1</span>Servicio
            </legend>
            <div className="choices">
              {services.map((s) => (
                <label className="choice" key={s.id}>
                  <input
                    type="radio"
                    name="service"
                    checked={serviceId === s.id}
                    onChange={() => chooseService(s.id)}
                  />
                  <span className="choice-name">{s.name}</span>
                  <span className="choice-meta">
                    {duration(s.duration_minutes)}, {money(s.price)}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="step area-day">
            <legend>
              <span className="step-n">2</span>Día
            </legend>
            <div className="days">
              {DAYS.map((d) => {
                const { weekday, num, month } = dayParts(d)
                return (
                  <button
                    type="button"
                    key={d}
                    className="day"
                    aria-pressed={d === day}
                    onClick={() => chooseDay(d)}
                  >
                    <span className="wd">{weekday}</span>
                    <span className="num">{num}</span>
                    <span className="wd">{month}</span>
                  </button>
                )
              })}
            </div>
          </fieldset>

          <div className="agenda area-agenda">
            <div className="agenda-head">
              <h3>
                <span className="step-n">3</span>Hora
              </h3>
              <p className="muted" aria-live="polite">
                {service
                  ? `${longDay(day)}. Las horas rayadas ya están ocupadas.`
                  : 'Elige un servicio para ver las horas libres.'}
              </p>
            </div>

            {notice && (
              <p className="notice" role="alert">
                {notice}
              </p>
            )}
            {slotsError && (
              <div className="notice" role="alert">
                {slotsError}{' '}
                <button type="button" className="btn-text" onClick={() => setReload((n) => n + 1)}>
                  Reintentar
                </button>
              </div>
            )}
            {service && slots === null && !slotsError && (
              <p className="muted agenda-msg" role="status">
                Buscando horas libres…
              </p>
            )}
            {noSlotsToday && (
              <p className="agenda-msg" role="status">
                No quedan horas libres este día. Prueba con otro día.
              </p>
            )}

            <div className={`agenda-grid${service && slots ? '' : ' is-idle'}`}>
              {HOURS.map((h) => (
                <div className="agenda-row" key={h}>
                  <span className="agenda-hour">{hourLabel(h)}</span>
                  {['00', '30'].map((mm) => {
                    const iso = available.get(`${pad(h)}:${mm}`)
                    const selected = Boolean(iso) && iso === picked
                    return (
                      <button
                        type="button"
                        key={mm}
                        className="slot"
                        disabled={!iso}
                        aria-pressed={selected}
                        aria-label={`${chipLabel(h, mm)} ${h < 12 ? 'am' : 'pm'}${iso ? '' : ', no disponible'}`}
                        onClick={() => chooseSlot(iso)}
                      >
                        {chipLabel(h, mm)}
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
          </div>

          {picked && service && (
            <form className="form area-form" ref={formRef} onSubmit={submit} noValidate>
              <fieldset className="step">
                <legend>
                  <span className="step-n">4</span>Tus datos
                </legend>
                <p className="summary">
                  <strong>{service.name}</strong>
                  <br />
                  {longDay(day)}, de {timeLabel(picked)} a{' '}
                  {timeLabel(addMinutes(picked, service.duration_minutes))}
                </p>

                {user ? (
                  <p className="muted as-user">
                    Reservando como <strong>{user.name}</strong> ({user.phone})
                  </p>
                ) : (
                  <>
                <div className="field">
                  <label htmlFor="name">Nombre</label>
                  <input
                    id="name"
                    autoComplete="name"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    aria-invalid={Boolean(errors.name)}
                    aria-describedby={errors.name ? 'name-err' : undefined}
                  />
                  {errors.name && (
                    <p className="err" id="name-err">
                      {errors.name}
                    </p>
                  )}
                </div>

                <div className="field">
                  <label htmlFor="phone">WhatsApp</label>
                  <input
                    id="phone"
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    aria-invalid={Boolean(errors.phone)}
                    aria-describedby={errors.phone ? 'phone-err' : undefined}
                  />
                  {errors.phone && (
                    <p className="err" id="phone-err">
                      {errors.phone}
                    </p>
                  )}
                </div>
                  </>
                )}

                <button type="submit" className="btn btn-primary btn-block" disabled={sending}>
                  {sending ? 'Reservando…' : 'Reservar cita'}
                </button>
              </fieldset>
            </form>
          )}
        </div>
      </div>
    </section>
  )
}
