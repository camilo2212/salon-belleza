import { ADMIN_URL, SALON } from '../config'

export default function Footer() {
  return (
    <footer id="contacto" className="footer">
      <div className="wrap">
        <h2>Visítanos</h2>
        <dl className="facts">
          {SALON.address && (
            <div>
              <dt>Dirección</dt>
              <dd>{SALON.address}</dd>
            </div>
          )}
          <div>
            <dt>Horario</dt>
            <dd>{SALON.hours}</dd>
          </div>
        </dl>
        {SALON.whatsapp && (
          <a
            className="btn btn-light"
            href={`https://wa.me/${SALON.whatsapp}`}
            target="_blank"
            rel="noreferrer"
          >
            Escribir por WhatsApp
          </a>
        )}
        <p className="legal">
          © {new Date().getFullYear()} {SALON.name} ·{' '}
          <a href={ADMIN_URL}>Acceso administración</a>
        </p>
      </div>
    </footer>
  )
}
