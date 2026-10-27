import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/client'
import { isHttpsUrl, keepsButtonDisabled, portalErrorKey } from './portalUrl'

describe('isHttpsUrl', () => {
  it('https の URL だけ、移ってよい', () => {
    expect(isHttpsUrl('https://billing.stripe.com/p/session/test_abc')).toBe(true)
  })

  it('http・javascript:・相対の URL・空には移らない', () => {
    expect(isHttpsUrl('http://billing.stripe.com/p/session/test_abc')).toBe(false)
    expect(isHttpsUrl('javascript:alert(1)')).toBe(false)
    expect(isHttpsUrl('/admin/billing')).toBe(false)
    expect(isHttpsUrl('')).toBe(false)
  })
})

describe('keepsButtonDisabled', () => {
  it('開いている間は、URL をもらったあと（成功）も、押せないままにする', () => {
    expect(keepsButtonDisabled('pending')).toBe(true)
    expect(keepsButtonDisabled('success')).toBe(true)
  })

  it('始める前と、開けなかったとき（失敗）は、押せる', () => {
    expect(keepsButtonDisabled('idle')).toBe(false)
    expect(keepsButtonDisabled('error')).toBe(false)
  })
})

describe('portalErrorKey', () => {
  it('Stripe を呼べなかったとき（502）は、管理画面用の、ふりがな付きの文言にする', () => {
    const error = new ApiError(
      502,
      'payment_service_unavailable',
      'error.payment_service_unavailable',
    )

    expect(portalErrorKey(error)).toBe('billing.portal_unavailable')
  })

  it('ほかのエラーは、API が返したキーのまま。API のエラーでなければ server_error', () => {
    expect(
      portalErrorKey(new ApiError(409, 'billing_not_connected', 'error.billing_not_connected')),
    ).toBe('error.billing_not_connected')
    expect(portalErrorKey(new Error('invalid portal url'))).toBe('error.server_error')
  })
})
