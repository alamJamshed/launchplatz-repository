import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Alert, AuthLayout, Button, TextField } from '../components'
import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../lib/api'

export function LoginPage() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  if (user) return <Navigate to="/" replace />
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setLoading(true); setError('')
    try { await login(email, password); navigate((location.state as { from?: string } | null)?.from || '/', { replace: true }) }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : 'Login failed.') }
    finally { setLoading(false) }
  }
  return <AuthLayout title="Welcome back" description="Sign in with your LaunchPlatz Admin account."><form className="gallery-form" onSubmit={submit}>{error && <Alert tone="danger">{error}</Alert>}<TextField id="email" label="Email address" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /><TextField id="password" label="Password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><Button type="submit" loading={loading}>Sign in</Button></form></AuthLayout>
}
