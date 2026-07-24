import { useState } from 'react'
import { Button, Card, TextField } from '../components'
import { api, ApiError } from '../lib/api'
import { formatDate } from '../lib/format'
import { useResource } from '../hooks/useResource'
import type { Project, RoutingRoute } from '../types'
import { Notice, RequestState, StatusBadge } from './shared'
import { ProjectFrame } from './ProjectFrame'

type RouteForm = {
  hostname: string
  service_name: string
  internal_port: string
  desired_enabled: boolean
  tls_enabled: boolean
}

export function RoutingPage() {
  return <ProjectFrame active="routing">{(project) => <RoutingWorkspace project={project} />}</ProjectFrame>
}

function RoutingWorkspace({ project }: { project: Project }) {
  const resource = useResource<RoutingRoute[]>((signal) => api.get(`/routing/routes/?project=${project.id}`, signal), [project.id])
  const route = resource.data?.[0]
  return <RequestState loading={resource.loading} error={resource.error}>
    <RoutingEditor key={route?.updated_at || 'new'} project={project} route={route} refetch={resource.refetch} />
  </RequestState>
}

function RoutingEditor({ project, route, refetch }: { project: Project; route?: RoutingRoute; refetch: () => Promise<unknown> }) {
  const [form, setForm] = useState<RouteForm>(route
    ? { hostname: route.hostname, service_name: route.service_name, internal_port: String(route.internal_port), desired_enabled: route.desired_enabled, tls_enabled: route.tls_enabled }
    : { hostname: '', service_name: project.django_service_name, internal_port: '8000', desired_enabled: true, tls_enabled: false })
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ tone: 'success' | 'danger' | 'info'; message: string } | null>(null)

  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setNotice(null)
    const payload = { project: project.id, ...form, internal_port: Number(form.internal_port) }
    try {
      if (route) await api.patch(`/routing/routes/${route.id}/`, payload)
      else await api.post('/routing/routes/', payload)
      await refetch()
      setNotice({ tone: 'success', message: 'Routing configuration saved.' })
    } catch (reason) {
      setNotice({ tone: 'danger', message: (reason as ApiError).message })
    } finally { setBusy(false) }
  }
  const action = async (name: 'verify-dns' | 'reconcile') => {
    if (!route) return
    setBusy(true)
    try {
      await api.post(`/routing/routes/${route.id}/${name}/`)
      await refetch()
      setNotice({ tone: 'success', message: name === 'verify-dns' ? 'DNS check completed. A second successful check is required.' : 'Reconciliation queued.' })
    } catch (reason) {
      setNotice({ tone: 'danger', message: (reason as Error).message })
    } finally { setBusy(false) }
  }

  return <>
    <Notice value={notice} />
    <div className="app-two-column">
      <Card className="app-detail-card">
        <h2>Route configuration</h2>
        <form className="gallery-form" onSubmit={save}>
          <TextField id="route-hostname" label="Local hostname" hint="Use a hostname resolved by your internal DNS." value={form.hostname} onChange={(event) => setForm({ ...form, hostname: event.target.value })} required />
          <div className="gallery-form-grid">
            <TextField id="route-service" label="Compose service" value={form.service_name} onChange={(event) => setForm({ ...form, service_name: event.target.value })} required />
            <TextField id="route-port" label="Internal HTTP port" type="number" min={1} max={65535} value={form.internal_port} onChange={(event) => setForm({ ...form, internal_port: event.target.value })} required />
          </div>
          <label className="app-checkbox"><input type="checkbox" checked={form.desired_enabled} onChange={(event) => setForm({ ...form, desired_enabled: event.target.checked })} /> Enable HTTP routing</label>
          <label className="app-checkbox"><input type="checkbox" checked={form.tls_enabled} disabled={!route || route.dns_status !== 'verified'} onChange={(event) => setForm({ ...form, tls_enabled: event.target.checked })} /> Enable Pebble test HTTPS</label>
          <Button type="submit" loading={busy} disabled={project.is_archived}>Save route</Button>
        </form>
      </Card>
      <Card className="app-detail-card">
        <h2>Observed state</h2>
        {route ? <><dl>
          <dt>Expected DNS address</dt><dd>{route.expected_address}</dd>
          <dt>Resolved addresses</dt><dd>{route.resolved_addresses.join(', ') || 'None'}</dd>
          <dt>DNS</dt><dd><StatusBadge status={route.dns_status} /></dd>
          <dt>Proxy</dt><dd><StatusBadge status={route.observed_status} /></dd>
          <dt>Last DNS check</dt><dd>{formatDate(route.dns_last_checked_at)}</dd>
          <dt>Last reconciliation</dt><dd>{formatDate(route.last_reconciled_at)}</dd>
        </dl>
        {route.dns_error && <p>{route.dns_error}</p>}
        {route.last_error && <p>{route.last_error}</p>}
        <div className="app-row-actions"><Button variant="secondary" loading={busy} onClick={() => void action('verify-dns')}>Verify DNS</Button><Button loading={busy} disabled={!project.git_cloned_at} onClick={() => void action('reconcile')}>Reconcile</Button></div></> : <p>Save a route to view DNS and proxy state.</p>}
      </Card>
    </div>
  </>
}
