import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest, setAccessToken } from './api'

const response = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => { vi.unstubAllGlobals(); setAccessToken(null) })

describe('API client', () => {
  it('unwraps the response envelope and sends the access token', async () => {
    setAccessToken('token')
    const fetchMock = vi.fn().mockResolvedValue(response(200, { success: true, data: { id: 1 } }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(apiRequest('/dashboard/')).resolves.toEqual({ id: 1 })
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('Authorization')).toBe('Bearer token')
  })

  it('normalizes backend failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(409, { success: false, message: 'Busy', errors: { category: 'conflict' } })))
    await expect(apiRequest('/projects/', { auth: false })).rejects.toMatchObject({ status: 409, message: 'Busy', category: 'conflict' } satisfies Partial<ApiError>)
  })

  it('coordinates refresh and retries concurrent 401 responses once', async () => {
    setAccessToken('expired')
    let protectedCalls = 0
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith('/auth/refresh/')) return response(200, { success: true, data: { access: 'new-token' } })
      protectedCalls += 1
      return protectedCalls <= 2 ? response(401, { success: false, message: 'Expired' }) : response(200, { success: true, data: { ok: true } })
    })
    vi.stubGlobal('fetch', fetchMock)
    await expect(Promise.all([apiRequest('/one/'), apiRequest('/two/')])).resolves.toEqual([{ ok: true }, { ok: true }])
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/refresh/'))).toHaveLength(1)
  })
})
