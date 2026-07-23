import { describe, expect, it } from 'vitest'
import { shouldPollContainers, shouldPollDeployment } from './polling'

describe('polling decisions', () => {
  it('polls only active deployments on visible pages', () => {
    expect(shouldPollDeployment('running')).toBe(true)
    expect(shouldPollDeployment('success')).toBe(false)
    expect(shouldPollDeployment('pending', false)).toBe(false)
  })

  it('pauses container polling on hidden pages', () => {
    expect(shouldPollContainers()).toBe(true)
    expect(shouldPollContainers(false)).toBe(false)
  })
})
