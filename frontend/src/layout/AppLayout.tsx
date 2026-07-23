import { CloudCog, FolderGit2, History, Rocket, Server, Settings } from 'lucide-react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { DashboardLayout, type NavItem } from '../components'
import { useAuth } from '../auth/AuthContext'

const nav: NavItem[] = [
  { id: '/', label: 'Overview', icon: <CloudCog /> },
  { id: '/servers', label: 'Servers', icon: <Server /> },
  { id: '/projects', label: 'Projects', icon: <FolderGit2 /> },
  { id: '/deployments', label: 'Deployments', icon: <Rocket /> },
  { id: '/deployment-history', label: 'History', icon: <History /> },
  { id: '/settings', label: 'Settings', icon: <Settings /> },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const active = nav.find((item) => item.id !== '/' && location.pathname.startsWith(item.id))?.id || '/'
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || 'Admin'
  return <DashboardLayout userName={name} nav={nav} activeId={active} onNavigate={navigate} onLogout={() => void logout()}><Outlet /></DashboardLayout>
}

export const projectTabs = [
  ['overview', 'Overview'], ['git', 'Git'], ['environment', 'Environment'], ['deployments', 'Deployments'], ['containers', 'Containers'],
] as const

export function ProjectTabs({ projectId, active }: { projectId: number; active: string }) {
  const navigate = useNavigate()
  return <nav className="app-tabs" aria-label="Project workspace">{projectTabs.map(([id, label]) => <button type="button" className={active === id ? 'active' : ''} key={id} onClick={() => navigate(`/projects/${projectId}/${id}`)}>{label}</button>)}</nav>
}
