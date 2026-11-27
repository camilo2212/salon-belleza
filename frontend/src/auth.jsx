import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, tokenStore } from './api'

const AuthContext = createContext(null)

// Sesión de la clienta. `user` es null si no ha ingresado.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)

  // Si quedó una sesión guardada, la recuperamos al abrir la página.
  useEffect(() => {
    if (!tokenStore.get()) return
    const ctrl = new AbortController()
    api
      .me(ctrl.signal)
      .then(setUser)
      .catch((err) => {
        // Solo un 401 significa "sesión vencida". Sin internet se conserva el token.
        if (!ctrl.signal.aborted && err.status === 401) tokenStore.clear()
      })
    return () => ctrl.abort()
  }, [])

  const start = useCallback((res) => {
    tokenStore.set(res.token)
    setUser(res.user)
  }, [])

  const value = useMemo(
    () => ({
      user,
      login: async (phone, password) => start(await api.login({ phone, password })),
      register: async (body) => start(await api.register(body)),
      logout: async () => {
        try {
          await api.logout() // invalida el token en el servidor
        } catch {
          /* aunque falle, se cierra la sesión en este navegador */
        }
        tokenStore.clear()
        setUser(null)
      },
      // El servidor dijo que la sesión ya no sirve.
      expire: () => {
        tokenStore.clear()
        setUser(null)
      },
    }),
    [user, start],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
