import type { BadgeTone } from '../components'

export function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function formatDuration(milliseconds?: number | null) {
  if (!milliseconds) return '—'
  if (milliseconds < 1000) return `${milliseconds} ms`
  return `${(milliseconds / 1000).toFixed(1)} s`
}

export function statusTone(status?: string): BadgeTone {
  const value = status?.toLowerCase()
  if (['success', 'online', 'healthy', 'running', 'deployed'].includes(value || '')) return 'success'
  if (['failed', 'offline', 'unhealthy', 'exited', 'cancelled'].includes(value || '')) return 'danger'
  if (['pending', 'cancelling', 'starting', 'unknown'].includes(value || '')) return 'warning'
  return 'neutral'
}

export function fieldErrors(errors: unknown): Record<string, string> {
  if (!errors || typeof errors !== 'object') return {}
  const source = errors as Record<string, unknown>
  const nested = source.errors && typeof source.errors === 'object' ? source.errors as Record<string, unknown> : source
  return Object.fromEntries(Object.entries(nested).map(([key, value]) => [key, Array.isArray(value) ? value.join(' ') : typeof value === 'object' && value ? JSON.stringify(value) : String(value)]))
}
