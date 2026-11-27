import { useEffect, useState } from 'react'
import { api, errorMessage } from './api'
import { SALON } from './config'
import Hero from './components/Hero'
import Services from './components/Services'
import Booking from './components/Booking'
import Products from './components/Products'
import Footer from './components/Footer'

export default function App() {
  const [services, setServices] = useState(null)
  const [servicesError, setServicesError] = useState('')
  const [products, setProducts] = useState(null)
  const [attempt, setAttempt] = useState(0)
  // Lo que la clienta eligió fuera del formulario (un servicio o una hora del inicio).
  const [intent, setIntent] = useState(null)

  useEffect(() => {
    const ctrl = new AbortController()
    setServicesError('')
    api
      .services(ctrl.signal)
      .then(setServices)
      .catch((e) => !ctrl.signal.aborted && setServicesError(errorMessage(e)))
    api
      .products(ctrl.signal)
      .then(setProducts)
      .catch(() => !ctrl.signal.aborted && setProducts([]))
    return () => ctrl.abort()
  }, [attempt])

  // Lleva a la clienta a la reserva, con el servicio o la hora ya elegidos si los hay.
  function goToBooking(choice = {}) {
    setIntent({ ...choice, id: Date.now() })
    document.getElementById('reservar')?.scrollIntoView()
  }

  const hasServices = Array.isArray(services) && services.length > 0

  return (
    <>
      <header className="header">
        <div className="wrap">
          <a className="brand" href="#top">
            {SALON.name}
          </a>
          <nav className="nav" aria-label="Principal">
            <a href="#servicios">Servicios</a>
            {Array.isArray(products) && products.length > 0 && <a href="#productos">Productos</a>}
            <a href="#contacto">Contacto</a>
            <a className="btn btn-primary" href="#reservar">
              Reservar cita
            </a>
          </nav>
        </div>
      </header>

      <main id="top">
        <Hero services={services} onPick={goToBooking} />
        <Services
          services={services}
          error={servicesError}
          onRetry={() => setAttempt((n) => n + 1)}
          onPick={goToBooking}
        />
        {hasServices && <Booking services={services} intent={intent} />}
        <Products products={products} />
      </main>

      <Footer />
    </>
  )
}
