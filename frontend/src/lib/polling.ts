import type { DeploymentStatus } from '../types'

export const ACTIVE_DEPLOYMENT_STATUSES: DeploymentStatus[] = ['pending', 'running', 'cancelling']
export function shouldPollDeployment(status?: DeploymentStatus, visible = true) { return Boolean(visible && status && ACTIVE_DEPLOYMENT_STATUSES.includes(status)) }
export function shouldPollContainers(visible = true) { return visible }
