import type { QueryClient } from '@tanstack/react-query'
import { api, messageKeyOf } from '../api/client'

// 開発用のユーザー切り替えの、切り替える処理（画面は DevUserSwitcher.tsx。spec 001 の research.md R-02）
export const DEV_USERS_QUERY_KEY = ['dev', 'users'] as const

type SwitchDeps = {
  queryClient: QueryClient
  navigate: (to: string) => void | Promise<void>
  close: () => void
}

/** 切り替える。うまくいったらシートを閉じ、最初の画面へ移る。失敗したらエラーの文言のキーを返す（シートは開いたまま） */
export async function switchDevUser(userId: number, deps: SwitchDeps): Promise<string | null> {
  try {
    await api.post('/api/dev/switch-user', { user_id: userId })
  } catch (error) {
    return messageKeyOf(error)
  }
  // 前の人のデータを画面に残さない（読み込んだものを捨ててから、最初の画面へ）。
  // 人の一覧は、だれがログインしていても同じなので残す
  deps.queryClient.removeQueries({
    predicate: (query) => query.queryKey[0] !== DEV_USERS_QUERY_KEY[0],
  })
  deps.close()
  void deps.navigate('/')
  return null
}
