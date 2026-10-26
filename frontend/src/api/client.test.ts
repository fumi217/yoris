import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './client'

function mockFetch(status: number, body?: unknown) {
  const fetchMock = vi
    .fn()
    .mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api', () => {
  it('読むときは X-Requested-With を付けない', async () => {
    const fetchMock = mockFetch(200, { status: 'ok' })

    await expect(api.get('/api/health')).resolves.toEqual({ status: 'ok' })
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('X-Requested-With')
  })

  it('書き込みには X-Requested-With: fetch と JSON の本文を付ける', async () => {
    const fetchMock = mockFetch(204)

    await expect(api.post('/api/dev/switch-user', { user_id: 1 })).resolves.toBeUndefined()
    const init = fetchMock.mock.calls[0][1]
    expect(init.method).toBe('POST')
    expect(init.headers).toMatchObject({
      'X-Requested-With': 'fetch',
      'Content-Type': 'application/json',
    })
    expect(init.body).toBe('{"user_id":1}')
  })

  it('エラーは ApiError にして、message_key を渡す', async () => {
    mockFetch(403, { error: { code: 'forbidden', message_key: 'error.forbidden' } })

    const error = await api.get('/api/admin/disclosure').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 403, code: 'forbidden', messageKey: 'error.forbidden' })
  })

  it('決まった形でないエラーは server_error にする', async () => {
    mockFetch(502)

    await expect(api.get('/api/me')).rejects.toMatchObject({
      status: 502,
      messageKey: 'error.server_error',
    })
  })

  it('つながらないときも server_error にする', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(api.get('/api/me')).rejects.toMatchObject({
      status: 0,
      messageKey: 'error.server_error',
    })
  })
})
