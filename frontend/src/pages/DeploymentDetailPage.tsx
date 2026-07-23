import { useParams } from 'react-router-dom'
import { PageHeading } from '../components'
import { api } from '../lib/api'
import { shouldPollDeployment } from '../lib/polling'
import { useResource } from '../hooks/useResource'
import type { Deployment } from '../types'
import { DeploymentSteps, DeploymentSummary } from './DeploymentComponents'
import { Notice, RequestState } from './shared'

export function DeploymentDetailPage() { const id = Number(useParams().deploymentId); const first = useResource<Deployment>((signal) => api.get(`/deployments/${id}/`, signal), [id]); const poll = shouldPollDeployment(first.data?.status) ? 3000 : undefined; const live = useResource<Deployment>((signal) => api.get(`/deployments/${id}/`, signal), [id], poll); const deployment = live.data || first.data; return <><PageHeading title={`Deployment #${id}`} description={deployment ? `${deployment.project_name_snapshot || `Project ${deployment.project}`} · ${deployment.trigger}` : 'Loading deployment audit…'} /><RequestState loading={first.loading && live.loading} error={first.error || live.error}>{deployment && <><DeploymentSummary deployment={deployment} />{deployment.error_message && <Notice value={{ tone: 'danger', message: deployment.error_message }} />}<section className="app-section"><h2>Ordered steps</h2><DeploymentSteps steps={deployment.steps} /></section></>}</RequestState></> }
