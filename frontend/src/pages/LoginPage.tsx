import { Navigate } from 'react-router'
import { homePathFor, useMeState } from '../auth/me'
import { Message } from '../components/Message'

/** ログインの画面（仮）。本物のログインのフォームは #65（001-T022）で作る。開発中は右下の切り替えを使う。 */
export function LoginPage() {
  const state = useMeState()
  if (state.status === 'loading') return <Message k="layout.loading" />
  if (state.status === 'error') return <Message k={state.messageKey} />
  if (state.me === null) return <Message k="layout.login_required" />
  // ログインしているのに、開ける画面がない（知らない役割など）
  const home = homePathFor(state.me)
  if (home === '/login') return <Message k="error.forbidden" />
  return <Navigate to={home} replace />
}
