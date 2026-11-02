import { describe, expect, it } from 'vitest'
import { ApiError } from './api/client'
import { ME_QUERY_KEY, type Me } from './auth/me'
import { createQueryClient } from './queryClient'

const me: Me = { kind: 'family', role: null, display_name: 'テスト 花子', language: 'ja' }

describe('createQueryClient', () => {
  it('どの API でも 401 が返ったら、ログイン中の人を「いない」にする', async () => {
    const queryClient = createQueryClient()
    queryClient.setQueryData(ME_QUERY_KEY, me)

    await queryClient
      .fetchQuery({
        queryKey: ['contact-book'],
        queryFn: () => Promise.reject(new ApiError(401, 'not_logged_in', 'error.not_logged_in')),
        retry: false,
      })
      .catch(() => undefined)

    expect(queryClient.getQueryData(ME_QUERY_KEY)).toBeNull()
  })

  it('401 でないエラーでは、ログイン中の人はそのまま', async () => {
    const queryClient = createQueryClient()
    queryClient.setQueryData(ME_QUERY_KEY, me)

    await queryClient
      .fetchQuery({
        queryKey: ['contact-book'],
        queryFn: () => Promise.reject(new ApiError(403, 'forbidden', 'error.forbidden')),
        retry: false,
      })
      .catch(() => undefined)

    expect(queryClient.getQueryData(ME_QUERY_KEY)).toEqual(me)
  })
})
