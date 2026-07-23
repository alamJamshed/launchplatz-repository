import { Link } from 'react-router-dom'
import { Card, DataTable, PageHeading, type TableColumn } from '../components'
import { api } from '../lib/api'
import { formatDate } from '../lib/format'
import { useResource } from '../hooks/useResource'
import type { DashboardData, Deployment } from '../types'
import { RequestState, StatusBadge } from './shared'

const columns: TableColumn<Deployment>[] = [
  { key: 'project', heading: 'Project', render: (row) => <Link to={`/deployments/${row.id}`}>{row.project_name_snapshot || `Project ${row.project}`}</Link> },
  { key: 'status', heading: 'Status', render: (row) => <StatusBadge status={row.status} /> },
  { key: 'trigger', heading: 'Trigger', render: (row) => row.trigger },
  { key: 'created', heading: 'Created', render: (row) => formatDate(row.created_at) },
]

export function DashboardPage() {
  const resource = useResource<DashboardData>((signal) => api.get('/dashboard/', signal), [])
  const data = resource.data
  return <><PageHeading title="Overview" description="Operational status across LaunchPlatz." /><RequestState loading={resource.loading} error={resource.error}>{data && <><div className="app-stat-grid"><Card className="app-stat"><span>Servers</span><strong>{data.servers.total}</strong><small>{data.servers.online} online · {data.servers.offline} offline</small></Card><Card className="app-stat"><span>Active projects</span><strong>{data.projects.active}</strong><small>{data.projects.archived} archived</small></Card><Card className="app-stat"><span>Active deployments</span><strong>{data.deployments.pending + data.deployments.running + data.deployments.cancelling}</strong><small>{data.deployments.failed} failed overall</small></Card></div><section className="app-section"><h2>Recent deployments</h2><DataTable caption="Recent deployments" columns={columns} rows={data.recent_deployments} rowKey={(row) => String(row.id)} /></section></>}</RequestState></>
}
