import { Alert, Badge, Skeleton } from '../components'
import type { ApiError } from '../lib/api'
import { statusTone } from '../lib/format'

export function RequestState({ loading, error, empty, children }: { loading: boolean; error?: ApiError | null; empty?: boolean; children: React.ReactNode }) {
  if (loading) return <Skeleton lines={5} />
  if (error) return <Alert tone="danger" title="Request failed">{error.message}</Alert>
  if (empty) return <Alert title="Nothing here yet">Create a record to get started.</Alert>
  return <>{children}</>
}

export function StatusBadge({ status }: { status: string }) { return <Badge tone={statusTone(status)}>{status.replaceAll('_', ' ')}</Badge> }
export function Notice({ value }: { value: { tone: 'success' | 'danger' | 'info'; message: string } | null }) { return value ? <div className="app-notice"><Alert tone={value.tone}>{value.message}</Alert></div> : null }
