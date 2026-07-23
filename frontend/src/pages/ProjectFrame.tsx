import type { ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { Badge, PageHeading } from '../components'
import { api } from '../lib/api'
import { useResource } from '../hooks/useResource'
import type { Project } from '../types'
import { ProjectTabs } from '../layout/AppLayout'
import { RequestState } from './shared'

export function ProjectFrame({ active, children }: { active: string; children: (project: Project, refetch: () => Promise<unknown>) => ReactNode }) {
  const projectId = Number(useParams().projectId)
  const resource = useResource<Project>((signal) => api.get(`/projects/${projectId}/`, signal), [projectId])
  return <RequestState loading={resource.loading} error={resource.error}>{resource.data && <><PageHeading title={resource.data.name} description={`${resource.data.framework_display} · ${resource.data.git_repository_url}`} action={resource.data.is_archived ? <Badge tone="warning">Archived</Badge> : undefined} /><ProjectTabs projectId={projectId} active={active} />{children(resource.data, resource.refetch)}</>}</RequestState>
}
