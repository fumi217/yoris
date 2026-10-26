// 画面で読み込んだデータの置き場所（TanStack Query）。
// どの API でも 401（セッションが切れた）が返ったら、ログイン中の人を「いない」にして、ログインの画面へ戻す
// （画面ごとに 401 を扱わなくて済むように。30 分の自動ログアウト #66 のあとも同じ）。
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from './api/client'
import { ME_QUERY_KEY } from './auth/me'

export function createQueryClient(): QueryClient {
  const onError = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401) {
      queryClient.setQueryData(ME_QUERY_KEY, null)
    }
  }
  const queryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
  })
  return queryClient
}
