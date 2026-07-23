import { describe, expect, it } from 'vitest'
import { fieldErrors, formatDuration, statusTone } from './format'

describe('formatters', () => {
  it('maps operational statuses to tones', () => {
    expect(statusTone('success')).toBe('success')
    expect(statusTone('failed')).toBe('danger')
    expect(statusTone('pending')).toBe('warning')
  })

  it('formats durations and validation errors', () => {
    expect(formatDuration(1500)).toBe('1.5 s')
    expect(fieldErrors({ email: ['Invalid.', 'Required.'] })).toEqual({ email: 'Invalid. Required.' })
  })
})
