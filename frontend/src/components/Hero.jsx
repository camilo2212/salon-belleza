import { useEffect, useState } from 'react'
import { api } from '../api'
import { SALON } from '../config'
import { dayLabel, nextDays, timeLabel } from '../format'

// Primera hora libre de cada uno de los próximos días, para el servicio dado.
function useNextSlots(service) {
  const [state, setState] = useState({ loading: true, items: [] })

  useEffect(() => {
    if (!service) return
    const ctrl = new AbortController()
    setState({ loading: true, items: [] })
    Promise.all(
      nextDays(5).map((day) =>
        api
          .availability(service.id, day, ctrl.signal)
          .then((data) => (data.slots[0] ? { day, iso: data.slots[0] } : null)),
      ),
    )
      .then((results) => setState({ loading: false, items: results.filter(Boolean).slice(0, 4) }))
      .catch(() => !ctrl.signal.aborted && setState({ loading: false, items: [] }))
    return () => ctrl.abort()
  }, [service?.id])

  return state
}

export default function Hero({ services, onPick }) {
  const first = Array.isArray(services) ? services[0] : null
  const { loading, items } = useNextSlots(first)

  return (
    <section className="hero">
      <div className="wrap">
        <div>
          <h1>{SALON.name}</h1>
          <p className="lede">{SALON.tagline}</p>
          <button type="button" className="btn btn-primary" onClick={() => onPick()}>
            Reservar cita
          </button>
        </div>

        {first && (
          <div className="next">
            <h2>Próximas horas libres para {first.name}</h2>
            {loading && <p className="muted">Buscando horas libres…</p>}
            {!loading && items.length === 0 && (
              <p className="muted">
                No hay horas libres en los próximos días. Elige otra fecha en la reserva.
              </p>
            )}
            {items.length > 0 && (
              <ul>
                {items.map(({ day, iso }) => (
                  <li key={iso}>
                    <button
                      type="button"
                      onClick={() => onPick({ serviceId: first.id, day, slot: iso })}
                    >
                      <span>{dayLabel(day)}</span>
                      <span className="when">{timeLabel(iso)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
