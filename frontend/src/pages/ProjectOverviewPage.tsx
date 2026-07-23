import { Link } from 'react-router-dom'
import { Button, Card } from '../components'
import { formatDate } from '../lib/format'
import { ProjectFrame } from './ProjectFrame'

export function ProjectOverviewPage() { return <ProjectFrame active="overview">{(project) => <div className="app-two-column"><Card className="app-detail-card"><h2>Configuration</h2><dl><dt>Server ID</dt><dd>{project.server}</dd><dt>Branch</dt><dd>{project.branch}</dd><dt>Compose file</dt><dd>{project.docker_compose_path}</dd><dt>Django service</dt><dd>{project.django_service_name}</dd><dt>Domain</dt><dd>{project.domain || 'Not configured'}</dd></dl></Card><Card className="app-detail-card"><h2>Git state</h2><dl><dt>Cloned</dt><dd>{formatDate(project.git_cloned_at)}</dd><dt>Current branch</dt><dd>{project.current_branch || '—'}</dd><dt>Current commit</dt><dd className="app-mono">{project.current_commit || '—'}</dd><dt>Last synced</dt><dd>{formatDate(project.last_git_synced_at)}</dd></dl><Button variant="secondary" onClick={() => undefined}><Link to={`/projects/${project.id}/git`}>Manage Git</Link></Button></Card></div>}</ProjectFrame> }
