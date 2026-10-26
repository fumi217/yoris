import { Navigate } from 'react-router'
import { homePathFor, useMeState } from '../auth/me'
import { Message } from '../components/Message'

/** / を開いたら、ログイン中の人の最初の画面へ（家族 → 連絡帳、職員 → 入居者一覧、事務員 → 管理画面）。 */
export function HomeRedirect() {
  const state = useMeState()
  if (state.status === 'loading') return <Message k="layout.loading" />
  if (state.status === 'error') return <Message k={state.messageKey} />
  return <Navigate to={homePathFor(state.me)} replace />
}
