import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, refreshAccessToken, setAccessToken, setSessionExpiredHandler } from '../lib/api'
import type { UserProfile } from '../types'

type AuthContextValue = { user: UserProfile | null; bootstrapping: boolean; login: (email: string, password: string) => Promise<void>; logout: () => Promise<void>; updateUser: (user: UserProfile) => void }
const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [bootstrapping, setBootstrapping] = useState(true)
  const clearSession = () => { setAccessToken(null); setUser(null) }
  useEffect(() => {
    setSessionExpiredHandler(clearSession)
    void refreshAccessToken().then(async (token) => {
      if (token) { try { setUser(await api.get<UserProfile>('/auth/profile/')) } catch { clearSession() } }
    }).finally(() => setBootstrapping(false))
    return () => setSessionExpiredHandler(null)
  }, [])
  const value = useMemo<AuthContextValue>(() => ({
    user, bootstrapping,
    login: async (email, password) => { const data = await api.post<{ access: string; user: UserProfile }>('/auth/login/', { email, password }, false); setAccessToken(data.access); setUser(data.user) },
    logout: async () => { try { await api.post('/auth/logout/', undefined, false) } finally { clearSession() } },
    updateUser: setUser,
  }), [user, bootstrapping])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('useAuth must be used inside AuthProvider'); return value }
