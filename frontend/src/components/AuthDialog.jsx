import { useEffect, useRef, useState } from 'react'
import { fieldErrors } from '../api'
import { useAuth } from '../auth'
import { SALON } from '../config'

const cleanPhone = (v) => v.replace(/[\s\-().]/g, '')

// Ventana para ingresar o crear cuenta. Es solo para clientas: administración está en /admin/.
export default function AuthDialog({ initialMode = 'login', onClose }) {
  const { login, register } = useAuth()
  const ref = useRef(null)
  const [mode, setMode] = useState(initialMode)
  const [form, setForm] = useState({ name: '', phone: '', password: '' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) dialog.showModal()
  }, [])

  function switchMode(next) {
    setMode(next)
    setErrors({})
  }

  async function submit(e) {
    e.preventDefault()
    const phone = cleanPhone(form.phone)
    const found = {}
    if (mode === 'register' && form.name.trim().length < 2) found.name = 'Escribe tu nombre.'
    if (!/^\+?\d{7,15}$/.test(phone)) {
      found.phone = 'Escribe tu número de WhatsApp solo con dígitos. Ejemplo: 3001234567'
    }
    if (mode === 'register' && form.password.length < 8) {
      found.password = 'Usa al menos 8 caracteres.'
    }
    if (mode === 'login' && !form.password) found.password = 'Escribe tu contraseña.'
    setErrors(found)
    if (Object.keys(found).length) return

    setBusy(true)
    try {
      if (mode === 'login') await login(phone, form.password)
      else await register({ name: form.name.trim(), phone, password: form.password })
      onClose()
    } catch (err) {
      setErrors(fieldErrors(err))
    } finally {
      setBusy(false)
    }
  }

  const isLogin = mode === 'login'
  const forgot = `https://wa.me/${SALON.whatsapp}?text=${encodeURIComponent(
    `Hola, olvidé mi contraseña de la página de ${SALON.name}. Mi número es ${cleanPhone(form.phone)}.`,
  )}`

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby="auth-title"
      onClose={onClose}
      onClick={(e) => e.target === ref.current && ref.current.close()}
    >
      <div className="dialog-head">
        <h2 id="auth-title">{isLogin ? 'Ingresar' : 'Crear cuenta'}</h2>
        <button type="button" className="btn-text" onClick={() => ref.current.close()}>
          Cerrar
        </button>
      </div>
      <p className="muted">
        No necesitas cuenta para reservar. Con cuenta ves y cancelas tus citas.
      </p>

      <div className="tabs" role="group" aria-label="Elige una opción">
        <button type="button" aria-pressed={isLogin} onClick={() => switchMode('login')}>
          Ya tengo cuenta
        </button>
        <button type="button" aria-pressed={!isLogin} onClick={() => switchMode('register')}>
          Soy nueva
        </button>
      </div>

      <form onSubmit={submit} noValidate>
        {errors.form && (
          <p className="notice" role="alert">
            {errors.form}
          </p>
        )}

        {!isLogin && (
          <Field id="auth-name" label="Nombre" error={errors.name}>
            <input
              id="auth-name"
              autoComplete="name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              aria-invalid={Boolean(errors.name)}
            />
          </Field>
        )}

        <Field id="auth-phone" label="WhatsApp" error={errors.phone}>
          <input
            id="auth-phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            aria-invalid={Boolean(errors.phone)}
          />
        </Field>

        <Field
          id="auth-password"
          label={isLogin ? 'Contraseña' : 'Crea una contraseña (mínimo 8 caracteres)'}
          error={errors.password}
        >
          <input
            id="auth-password"
            type="password"
            autoComplete={isLogin ? 'current-password' : 'new-password'}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            aria-invalid={Boolean(errors.password)}
          />
        </Field>

        <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'Un momento…' : isLogin ? 'Ingresar' : 'Crear mi cuenta'}
        </button>
      </form>

      {isLogin && SALON.whatsapp && (
        <p className="muted dialog-foot">
          ¿Olvidaste tu contraseña?{' '}
          <a href={forgot} target="_blank" rel="noreferrer">
            Escríbenos por WhatsApp
          </a>{' '}
          y te ayudamos.
        </p>
      )}
    </dialog>
  )
}

function Field({ id, label, error, children }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error && (
        <p className="err" id={`${id}-err`}>
          {error}
        </p>
      )}
    </div>
  )
}
