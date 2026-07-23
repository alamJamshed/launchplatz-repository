import type { ApiEnvelope, ApiFailure, Paginated } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
let accessToken: string | null = null
let refreshPromise: Promise<string | null> | null = null
let expiredHandler: (() => void) | null = null

export class ApiError extends Error {
  status: number
  errors: unknown
  category?: string
  constructor(message: string, status: number, errors?: unknown) {
    super(message)
    this.status = status
    this.errors = errors
    if (errors && typeof errors === 'object' && 'category' in errors) this.category = String((errors as { category: unknown }).category)
  }
}

export function setAccessToken(token: string | null) { accessToken = token }
export function setSessionExpiredHandler(handler: (() => void) | null) { expiredHandler = handler }

async function parseResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null) as ApiEnvelope<T> | ApiFailure | null
  if (!response.ok || !body || !body.success) {
    const failure = body as ApiFailure | null
    throw new ApiError(failure?.message || 'The request could not be completed.', response.status, failure?.errors)
  }
  return body.data
}

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise
  refreshPromise = fetch(`${API_BASE}/auth/refresh/`, { method: 'POST', credentials: 'include' })
    .then(async (response) => {
      const data = await parseResponse<{ access: string }>(response)
      setAccessToken(data.access)
      return data.access
    })
    .catch(() => { setAccessToken(null); return null })
    .finally(() => { refreshPromise = null })
  return refreshPromise
}

export async function apiRequest<T>(path: string, options: RequestInit & { auth?: boolean; retry?: boolean } = {}): Promise<T> {
  const { auth = true, retry = true, headers, ...init } = options
  const requestHeaders = new Headers(headers)
  if (init.body && !(init.body instanceof FormData)) requestHeaders.set('Content-Type', 'application/json')
  if (auth && accessToken) requestHeaders.set('Authorization', `Bearer ${accessToken}`)
  const response = await fetch(`${API_BASE}${path.startsWith('/') ? path : `/${path}`}`, { ...init, headers: requestHeaders, credentials: 'include' })
  if (response.status === 401 && auth && retry) {
    const token = await refreshAccessToken()
    if (token) return apiRequest<T>(path, { ...options, retry: false })
    expiredHandler?.()
  }
  return parseResponse<T>(response)
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => apiRequest<T>(path, { signal }),
  post: <T>(path: string, body?: unknown, auth = true) => apiRequest<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body), auth }),
  patch: <T>(path: string, body: unknown) => apiRequest<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) => apiRequest<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: 'DELETE' }),
}

export type { Paginated }
