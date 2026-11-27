import { duration, money } from '../format'
import { ErrorBox, Loading } from './Status'

export default function Services({ services, error, onRetry, onPick }) {
  return (
    <section id="servicios" className="section">
      <div className="wrap split">
        <div>
          <h2>Servicios</h2>
          <p className="lede">Elige uno y te mostramos las horas libres.</p>
        </div>

        <div>
          {error && <ErrorBox message={error} onRetry={onRetry} />}
          {!error && services === null && <Loading label="Cargando servicios…" />}
          {!error && services?.length === 0 && (
            <p className="status">Estamos preparando la lista de servicios. Vuelve pronto.</p>
          )}
          {services?.length > 0 && (
            <ul className="menu">
              {services.map((s) => (
                <li className="menu-item" key={s.id}>
                  <div className="menu-main">
                    <h3>{s.name}</h3>
                    <span className="leader" aria-hidden="true" />
                    <span className="price">{money(s.price)}</span>
                  </div>
                  {s.description && <p className="muted">{s.description}</p>}
                  <div className="menu-foot">
                    <span className="muted">{duration(s.duration_minutes)}</span>
                    <button
                      type="button"
                      className="btn-text"
                      aria-label={`Reservar ${s.name}`}
                      onClick={() => onPick({ serviceId: s.id })}
                    >
                      Reservar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
