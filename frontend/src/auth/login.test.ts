import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { createQueryClient } from '../queryClient'
import { logIn, logOut } from './login'
import { ME_QUERY_KEY, type Me } from './me'

const staff: Me = { kind: 'staff', role: 'leader', display_name: 'テストリーダー', language: 'ja' }
const family: Me = { kind: 'family', role: null, display_name: 'テストさんの母', language: 'ja' }

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

describe('logIn', () => {
  it('返ってきた人をログイン中の人にし、前の人のデータは捨てる', async () => {
    const queryClient = createQueryClient()
    queryClient.setQueryData(ME_QUERY_KEY, family)
    queryClient.setQueryData(['contact-book'], { note: '前の人の連絡帳' })
    const fetchMock = mockFetch(200, staff)

    await expect(logIn(queryClient, 's00001', 'kumoyama-sora')).resolves.toEqual(staff)

    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/login')
    expect(fetchMock.mock.calls[0][1].body).toBe('{"login":"s00001","password":"kumoyama-sora"}')
    expect(queryClient.getQueryData(ME_QUERY_KEY)).toEqual(staff)
    expect(queryClient.getQueryData(['contact-book'])).toBeUndefined()
  })

  it('パスワードが違えば login_failed を投げ、ログイン中の人は変えない', async () => {
    const queryClient = createQueryClient()
    queryClient.setQueryData(ME_QUERY_KEY, null)
    mockFetch(401, { error: { code: 'login_failed', message_key: 'error.login_failed' } })

    const error = await logIn(queryClient, 's00001', 'wrong-password').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).messageKey).toBe('error.login_failed')
    expect(queryClient.getQueryData(ME_QUERY_KEY)).toBeNull()
  })
})

describe('logOut', () => {
  it('ログイン中の人を「いない」にし、読み込んだデータを捨てる', async () => {
    const queryClient = createQueryClient()
    queryClient.setQueryData(ME_QUERY_KEY, staff)
    queryClient.setQueryData(['residents'], [{ id: 1 }])
    mockFetch(204)

    await logOut(queryClient)

    expect(queryClient.getQueryData(ME_QUERY_KEY)).toBeNull()
    expect(queryClient.getQueryData(['residents'])).toBeUndefined()
  })

  it('つながらなければ、ログインしたままにする', async () => {
    const queryClient = createQueryClient()
    queryClient.setQueryData(ME_QUERY_KEY, staff)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(logOut(queryClient)).rejects.toBeInstanceOf(ApiError)

    expect(queryClient.getQueryData(ME_QUERY_KEY)).toEqual(staff)
  })
})
