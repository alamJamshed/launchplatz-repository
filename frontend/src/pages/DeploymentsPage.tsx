import { PageHeading, DataTable } from '../components'
import { api, type Paginated } from '../lib/api'
import { useResource } from '../hooks/useResource'
import type { Deployment } from '../types'
import { deploymentColumns } from './DeploymentComponents'
import { RequestState } from './shared'

export function DeploymentsPage() { const resource = useResource<Paginated<Deployment>>((signal) => api.get('/deployments/?limit=100&ordering=newest', signal), [], 3000); const active = (resource.data?.results || []).filter((item) => ['pending', 'running', 'cancelling'].includes(item.status)); const recent = (resource.data?.results || []).slice(0, 10); return <><PageHeading title="Deployments" description="Monitor active runs and the latest operational results." /><section className="app-section"><h2>Active deployments</h2><RequestState loading={resource.loading} error={resource.error} empty={!active.length}><DataTable caption="Active deployments" columns={deploymentColumns} rows={active} rowKey={(row) => String(row.id)} /></RequestState></section><section className="app-section"><h2>Latest deployments</h2><RequestState loading={resource.loading} error={resource.error} empty={!recent.length}><DataTable caption="Latest deployments" columns={deploymentColumns} rows={recent} rowKey={(row) => String(row.id)} /></RequestState></section></> }
