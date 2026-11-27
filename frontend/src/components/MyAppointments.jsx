import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api'
import { useAuth } from '../auth'
import { SALON } from '../config'
import { longDayAt, timeLabel } from '../format'

const ACTIVE = ['pending', 'confirmed']

function Item({ appt, readOnly = false, confirming, busy, onAsk, onCancel, onKeep }) {
  const live = !readOnly && ACTIVE.includes(appt.status)
  return (
    <li className="appt">
      <div>
        <span className={`tag tag-${appt.status}`}>{appt.status_label}</span>
        <p className="appt-when">{longDayAt(appt.start)}</p>
        <p>
          {appt.service}, de {timeLabel(appt.start)} a {timeLabel(appt.end)}
        </p>
      </div>

      {live && appt.can_cancel && (
        <div className="appt-actions">
          {confirming ? (
            <>
              <span>¿Cancelar esta cita?</span>
              <button type="button" className="btn btn-primary" disabled={busy} onClick={onCancel}>
                {busy ? 'Cancelando…' : 'Sí, cancelar'}
              </button>
              <button type="button" className="btn btn-line" disabled={busy} onClick={onKeep}>
                No, conservarla
              </button>
            </>
          ) : (
            <button type="button" className="btn btn-line" onClick={onAsk}>
              Cancelar cita
            </button>
          )}
        </div>
      )}

      {live && !appt.can_cancel && (
        <p className="muted">
          Para cambiar o cancelar esta cita{' '}
          {SALON.whatsapp ? (
            <a href={`https://wa.me/${SALON.whatsapp}`} target="_blank" rel="noreferrer">
              escríbenos por WhatsApp
            </a>
          ) : (
            'escríbenos por WhatsApp'
          )}
          .
        </p>
      )}
    </li>
  )
}

// Sección "Mis citas": solo aparece con sesión iniciada.
export default function MyAppointments({ refreshKey }) {
  const { user, logout, expire } = useAuth()
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [confirming, setConfirming] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const ctrl = new AbortController()
    setError('')
    api
      .myAppointments(ctrl.signal)
      .then(setItems)
      .catch((err) => {
        if (ctrl.signal.aborted) return
        if (err.status === 401) expire()
        else setError(errorMessage(err))
      })
    return () => ctrl.abort()
  }, [refreshKey, reload, expire])

  async function cancel(appt) {
    setBusyId(appt.id)
    setNotice('')
    try {
      const updated = await api.cancelAppointment(appt.id)
      setItems((list) => list.map((a) => (a.id === updated.id ? updated : a)))
      setConfirming(null)
      setNotice('Listo, tu cita quedó cancelada.')
    } catch (err) {
      if (err.status === 401) expire()
      else {
        setConfirming(null)
        setNotice(errorMessage(err))
        setReload((n) => n + 1) // la lista puede haber cambiado
      }
    } finally {
      setBusyId(null)
    }
  }

  const now = Date.now()
  const upcoming = (items ?? [])
    .filter((a) => ACTIVE.includes(a.status) && new Date(a.end).getTime() > now)
    .sort((a, b) => new Date(a.start) - new Date(b.start))
  const past = (items ?? []).filter((a) => !upcoming.includes(a))

  return (
    <section id="mis-citas" className="section">
      <div className="wrap">
        <div className="account-head">
          <h2>Hola, {user.name}</h2>
          <button type="button" className="btn btn-line" onClick={logout}>
            Salir
          </button>
        </div>
        <p className="lede">Aquí ves las citas que reservaste con tu cuenta.</p>

        {notice && (
          <p className="notice notice-block" role="status">
            {notice}
          </p>
        )}
        {error && (
          <p className="notice notice-block" role="alert">
            {error}{' '}
            <button type="button" className="btn-text" onClick={() => setReload((n) => n + 1)}>
              Reintentar
            </button>
          </p>
        )}
        {items === null && !error && <p className="muted">Cargando tus citas…</p>}

        {items && upcoming.length === 0 && (
          <p className="muted account-empty">
            No tienes citas próximas. <a href="#reservar">Reservar una cita</a>
          </p>
        )}
        {upcoming.length > 0 && (
          <ul className="appts">
            {upcoming.map((a) => (
              <Item
                key={a.id}
                appt={a}
                confirming={confirming === a.id}
                busy={busyId === a.id}
                onAsk={() => setConfirming(a.id)}
                onKeep={() => setConfirming(null)}
                onCancel={() => cancel(a)}
              />
            ))}
          </ul>
        )}

        {past.length > 0 && (
          <details className="past">
            <summary>Citas anteriores ({past.length})</summary>
            <ul className="appts">
              {past.map((a) => (
                <Item key={a.id} appt={a} readOnly />
              ))}
            </ul>
          </details>
        )}
      </div>
    </section>
  )
}
