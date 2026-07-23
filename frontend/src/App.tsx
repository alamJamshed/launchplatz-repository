import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppLayout } from './layout/AppLayout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { ServersPage } from './pages/ServersPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ProjectOverviewPage } from './pages/ProjectOverviewPage'
import { GitPage } from './pages/GitPage'
import { EnvironmentPage } from './pages/EnvironmentPage'
import { ProjectDeploymentsPage } from './pages/ProjectDeploymentsPage'
import { ContainersPage } from './pages/ContainersPage'
import { DeploymentsPage } from './pages/DeploymentsPage'
import { DeploymentHistoryPage } from './pages/DeploymentHistoryPage'
import { DeploymentDetailPage } from './pages/DeploymentDetailPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<ProtectedRoute />}>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="servers" element={<ServersPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:projectId/overview" element={<ProjectOverviewPage />} />
        <Route path="projects/:projectId/git" element={<GitPage />} />
        <Route path="projects/:projectId/environment" element={<EnvironmentPage />} />
        <Route path="projects/:projectId/deployments" element={<ProjectDeploymentsPage />} />
        <Route path="projects/:projectId/containers" element={<ContainersPage />} />
        <Route path="deployments" element={<DeploymentsPage />} />
        <Route path="deployment-history" element={<DeploymentHistoryPage />} />
        <Route path="deployments/:deploymentId" element={<DeploymentDetailPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
