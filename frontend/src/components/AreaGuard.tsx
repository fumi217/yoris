import type { ReactNode } from 'react'
import { Navigate } from 'react-router'
import { canOpen, homePathFor, useMeState, type Area } from '../auth/me'
import { Message } from './Message'

/**
 * その画面のまとまり（家族・職員・管理画面）を開ける人だけに中身を出す。
 * 開けない人は、その人の最初の画面に戻す（家族が職員の URL を直接開いても、家族の画面に戻る）。
 */
export function AreaGuard({ area, children }: { area: Area; children: ReactNode }) {
  const state = useMeState()
  if (state.status === 'loading') return <Message k="layout.loading" />
  if (state.status === 'error') return <Message k={state.messageKey} />
  if (state.me === null || !canOpen(state.me, area)) {
    return <Navigate to={homePathFor(state.me)} replace />
  }
  return children
}
