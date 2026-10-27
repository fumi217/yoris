import { useMutation } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '../../api/client'
import { Text } from '../../components/Text'
import { isHttpsUrl, keepsButtonDisabled, portalErrorKey } from './portalUrl'

/**
 * 「お支払い方法の変更・解約・請求書の確認」のボタン（spec 002 の T039・FR-020）。
 * 押すと、Stripe の Customer Portal の入口の URL をもらって、その画面へ移る。
 * 移るまでの間（URL をもらったあとも）、「開いています」のまま、ボタンを押せなくする。
 * 画面そのものは作らない（Stripe が用意する）。
 */
export function PortalButton() {
  const open = useMutation({
    mutationFn: () => api.post<{ portal_url: string }>('/api/admin/billing/portal'),
    onSuccess: ({ portal_url }) => {
      if (!isHttpsUrl(portal_url)) throw new Error('invalid portal url')
      window.location.assign(portal_url)
    },
  })

  // ブラウザの「戻る」で、保存されたままのこの画面に戻ったときは、また押せるようにする
  const { reset } = open
  useEffect(() => {
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) reset()
    }
    window.addEventListener('pageshow', onPageShow)
    return () => window.removeEventListener('pageshow', onPageShow)
  }, [reset])

  return (
    <PortalButtonView
      opening={keepsButtonDisabled(open.status)}
      error={open.error}
      onOpen={open.mutate}
    />
  )
}

/** 見た目だけ（テストではこれを直接出す）。 */
export function PortalButtonView({
  opening,
  error,
  onOpen,
}: {
  opening: boolean
  error: unknown
  onOpen: () => void
}) {
  return (
    <div className="space-y-2 px-4 pb-4">
      {error != null && (
        <p role="alert" className="text-red-700">
          <Text k={portalErrorKey(error)} />
        </p>
      )}
      <button
        type="button"
        disabled={opening}
        onClick={onOpen}
        className="w-full rounded bg-sky-700 p-3 text-balance text-center font-bold text-white disabled:opacity-60 sm:w-auto"
      >
        <Text k={opening ? 'billing.portal_opening' : 'billing.portal_button'} />
      </button>
      <p className="text-sm text-gray-600">
        <Text k="billing.portal_note" />
      </p>
    </div>
  )
}
