// ログイン中の人（`GET /api/me`）と、役割ごとにどの画面を開けるか（spec 001 の T019・docs/画面設計.md「3」）。
// 画面で隠すのは見た目のためだけで、守りは API の 403（家族が職員の API を呼んでも読めない）。
import { useQuery } from '@tanstack/react-query'
import { ApiError, api, messageKeyOf } from '../api/client'

export type StaffRole = 'care_worker' | 'leader' | 'counselor' | 'clerk' | 'director'

export type Me = {
  kind: 'staff' | 'family'
  role: StaffRole | null
  display_name: string
  language: string
}

export type Area = 'family' | 'staff' | 'admin'

export const ME_QUERY_KEY = ['me'] as const

/** ログイン中の人。ログインしていなければ null。 */
export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      try {
        return await api.get<Me>('/api/me')
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }
    },
    // 画面を移るたびに呼び直さない（ログインの切り替え・401 のときは、すぐに入れ替える）
    staleTime: 60_000,
    // ログインしていない（401）は試し直さない。一時的な失敗は 2 回まで試し直す
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 401) && failureCount < 2,
  })
}

export type MeState =
  | { status: 'loading' }
  | { status: 'error'; messageKey: string }
  | { status: 'ready'; me: Me | null }

/**
 * ログイン中の人を待つ。画面の守り・最初の画面への振り分け・ログインの画面で使う。
 * 一度分かったあとに読み直しが失敗しても、前の値で画面を出し続ける（一瞬の通信の失敗で画面を消さない）。
 */
export function useMeState(): MeState {
  const me = useMe()
  if (me.data !== undefined) return { status: 'ready', me: me.data }
  if (me.isPending) return { status: 'loading' }
  return { status: 'error', messageKey: messageKeyOf(me.error) }
}

// 職員の画面（入居者一覧・記録・返事）：事務員は開けない
const STAFF_AREA_ROLES: StaffRole[] = ['care_worker', 'leader', 'counselor', 'director']
// 管理画面：生活相談員・施設長・事務員（中の画面ごとの役割は、各担当の API の 403 で絞る）
const ADMIN_AREA_ROLES: StaffRole[] = ['counselor', 'director', 'clerk']

export function canOpen(me: Me, area: Area): boolean {
  if (area === 'family') return me.kind === 'family'
  if (me.kind !== 'staff' || me.role === null) return false
  return (area === 'staff' ? STAFF_AREA_ROLES : ADMIN_AREA_ROLES).includes(me.role)
}

/** ログインしたあとに最初に開く画面。開けない画面の URL を開いたときも、ここに戻す。 */
export function homePathFor(me: Me | null): string {
  if (me === null) return '/login'
  if (canOpen(me, 'family')) return '/family'
  if (canOpen(me, 'staff')) return '/staff'
  if (canOpen(me, 'admin')) return '/admin'
  return '/login'
}
