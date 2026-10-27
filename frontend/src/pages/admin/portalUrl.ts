import { ApiError, messageKeyOf } from '../../api/client'

/** カードの変更・解約の画面は https の Stripe の画面だけ。それ以外の URL へは移らない。 */
export function isHttpsUrl(url: string): boolean {
  try {
    return new URL(url).protocol === 'https:'
  } catch {
    return false
  }
}

/**
 * ポータルを開く操作の間、ボタンを押せなくして「開いています」を出し続けるか。
 * 入口の URL をもらったあとも、ページが切り替わるまでは続ける（すぐ元に戻ると、押せるように見える）。
 */
export function keepsButtonDisabled(status: 'idle' | 'pending' | 'success' | 'error'): boolean {
  return status === 'pending' || status === 'success'
}

/**
 * ポータルを開けなかったときの文言の辞書のキー。
 * Stripe を呼べなかったとき（502）は、申し込みの画面用の文言（ふりがななし）ではなく、
 * 管理画面用の、ふりがな付きの文言を出す。ほかのエラーは、API が返したキーのまま。
 */
export function portalErrorKey(error: unknown): string {
  if (error instanceof ApiError && error.code === 'payment_service_unavailable') {
    return 'billing.portal_unavailable'
  }
  return messageKeyOf(error)
}
