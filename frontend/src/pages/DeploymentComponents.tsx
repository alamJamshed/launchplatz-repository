import { Link } from 'react-router-dom'
import { Badge, Card, DataTable, type TableColumn } from '../components'
import { formatDate, formatDuration } from '../lib/format'
import type { Deployment, DeploymentStep } from '../types'
import { StatusBadge } from './shared'

export const deploymentColumns: TableColumn<Deployment>[] = [
  { key: 'project', heading: 'Project', render: (row) => <Link to={`/deployments/${row.id}`}><strong>{row.project_name_snapshot || `Project ${row.project}`}</strong></Link> },
  { key: 'trigger', heading: 'Trigger', render: (row) => row.trigger },
  { key: 'status', heading: 'Status', render: (row) => <StatusBadge status={row.status} /> },
  { key: 'commit', heading: 'Commit', render: (row) => <span className="app-mono">{(row.deployed_commit || row.previous_commit || '—').slice(0, 10)}</span> },
  { key: 'duration', heading: 'Duration', render: (row) => formatDuration(row.duration_ms) },
  { key: 'created', heading: 'Created', render: (row) => formatDate(row.created_at) },
]

export function DeploymentSummary({ deployment }: { deployment: Deployment }) { return <div className="app-stat-grid"><Card className="app-stat"><span>Status</span><StatusBadge status={deployment.status} /></Card><Card className="app-stat"><span>Rollback</span><Badge>{deployment.rollback_status.replaceAll('_', ' ')}</Badge></Card><Card className="app-stat"><span>Duration</span><strong className="app-stat-small">{formatDuration(deployment.duration_ms)}</strong></Card></div> }

const stepColumns: TableColumn<DeploymentStep>[] = [{ key: 'step', heading: 'Step', render: (row) => <strong>{row.order}. {row.name.replaceAll('_', ' ')}</strong> }, { key: 'status', heading: 'Status', render: (row) => <StatusBadge status={row.status} /> }, { key: 'duration', heading: 'Duration', render: (row) => formatDuration(row.duration_ms) }, { key: 'error', heading: 'Result', render: (row) => row.error_message || row.error_category || '—' }]
export function DeploymentSteps({ steps = [] }: { steps?: DeploymentStep[] }) { return <DataTable caption="Deployment steps" columns={stepColumns} rows={steps} rowKey={(row) => String(row.id)} /> }
