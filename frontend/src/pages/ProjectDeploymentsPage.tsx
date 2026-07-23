import { useState } from 'react'
import { Button, ConfirmModal } from '../components'
import { api } from '../lib/api'
import { shouldPollDeployment } from '../lib/polling'
import { useResource } from '../hooks/useResource'
import type { Deployment, Project } from '../types'
import { ProjectFrame } from './ProjectFrame'
import { DeploymentSteps, DeploymentSummary } from './DeploymentComponents'
import { Notice, RequestState } from './shared'

function ProjectDeploymentsContent({ project }: { project: Project }) {
  const resource = useResource<Deployment | null>((signal) => api.get(`/projects/${project.id}/deployment-status/`, signal), [project.id], shouldPollDeployment(undefined) ? 3000 : undefined)
  const poll = shouldPollDeployment(resource.data?.status) ? 3000 : undefined
  const polled = useResource<Deployment | null>((signal) => api.get(`/projects/${project.id}/deployment-status/`, signal), [project.id], poll)
  const deployment = polled.data ?? resource.data; const loading = resource.loading && polled.loading
  const [busy, setBusy] = useState(false); const [cancel, setCancel] = useState(false); const [notice, setNotice] = useState<{ tone: 'success' | 'danger' | 'info'; message: string } | null>(null)
  const start = async (trigger: 'deploy' | 'redeploy') => { setBusy(true); try { await api.post(`/projects/${project.id}/${trigger}/`); setNotice({ tone: 'success', message: `${trigger === 'deploy' ? 'Deployment' : 'Redeployment'} queued.` }); await Promise.all([resource.refetch(), polled.refetch()]) } catch (reason) { setNotice({ tone: 'danger', message: (reason as Error).message }) } finally { setBusy(false) } }
  const cancelDeployment = async () => { if (!deployment) return; setBusy(true); try { await api.post(`/deployments/${deployment.id}/cancel/`); setCancel(false); setNotice({ tone: 'success', message: 'Cancellation requested.' }); await polled.refetch() } catch (reason) { setNotice({ tone: 'danger', message: (reason as Error).message }) } finally { setBusy(false) } }
  return <><Notice value={notice} /><div className="app-toolbar"><p>Deployments run asynchronously through the Celery worker.</p><div className="app-row-actions"><Button disabled={project.is_archived || !project.git_cloned_at || shouldPollDeployment(deployment?.status)} loading={busy} onClick={() => void start(deployment ? 'redeploy' : 'deploy')}>{deployment ? 'Redeploy' : 'Deploy'}</Button>{deployment && shouldPollDeployment(deployment.status) && <Button variant="danger" onClick={() => setCancel(true)}>Cancel deployment</Button>}</div></div><RequestState loading={loading} error={resource.error || polled.error} empty={!deployment}>{deployment && <><DeploymentSummary deployment={deployment} />{deployment.error_message && <Notice value={{ tone: 'danger', message: deployment.error_message }} />}<section className="app-section"><h2>Pipeline steps</h2><DeploymentSteps steps={deployment.steps} /></section></>}</RequestState><ConfirmModal open={cancel} title="Cancel deployment?" description="Cancellation is cooperative and may trigger code and container rollback." confirmLabel="Request cancellation" danger loading={busy} onClose={() => setCancel(false)} onConfirm={() => void cancelDeployment()} /></>
}
export function ProjectDeploymentsPage() { return <ProjectFrame active="deployments">{(project) => <ProjectDeploymentsContent project={project} />}</ProjectFrame> }
