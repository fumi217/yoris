// 本物のログイン・ログアウト（spec 001 の T022・T097）。
// どちらも、前の人のデータを画面に残さないように、読み込んだものを捨ててから、ログイン中の人を入れ替える。
// API は useMutation を通さずに呼ぶ（ログインの 401 は「パスワードが違う」なので、
// queryClient.ts の「401 ならログインの画面へ戻す」しくみに乗せない）。
import type { QueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ME_QUERY_KEY, type Me } from './me'

function switchMe(queryClient: QueryClient, me: Me | null) {
  // ログイン中の人だけは消さずに中身を入れ替える
  // （消すと、いま開いている画面が入れ替わりに気づかず、次の画面へ移らない）
  queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_QUERY_KEY[0] })
  queryClient.setQueryData(ME_QUERY_KEY, me)
}

/** ログインする。返ってきた人（GET /api/me と同じ中身）を、そのままログイン中の人にする。 */
export async function logIn(queryClient: QueryClient, login: string, password: string) {
  const me = await api.post<Me>('/api/auth/login', { login, password })
  switchMe(queryClient, me)
  return me
}

/**
 * ログアウトする。失敗したら（つながらないなど）ApiError を投げ、画面はログインしたままにする
 * （共有のタブレットで、サーバーにセッションが残ったまま「ログアウトした」ように見せない）。
 */
export async function logOut(queryClient: QueryClient) {
  await api.post('/api/auth/logout')
  switchMe(queryClient, null)
}
