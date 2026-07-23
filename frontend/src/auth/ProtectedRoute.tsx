import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Spinner } from '../components'
import { useAuth } from './AuthContext'

export function ProtectedRoute() {
  const { user, bootstrapping } = useAuth()
  const location = useLocation()
  if (bootstrapping) return <main className="app-loading"><Spinner size="large" /><p>Restoring your session…</p></main>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}
