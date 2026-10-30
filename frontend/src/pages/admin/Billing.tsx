import { useQuery } from '@tanstack/react-query'
import { Icon } from '../../components/Icon'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { PortalButton } from './PortalButton'

export type BillingInfo = {
  status: 'active' | 'payment_failed' | 'cancel_scheduled' | 'canceled'
  plan_name: string
  amount_jpy: number
  current_period_end: string | null
  cancel_at: string | null
  can_subscribe: boolean
  can_manage: boolean
}

/**
 * 利用料のお支払い（`/admin/billing`。施設長・事務員。spec 002 の T026・FR-018）。
 * 契約の状態とプラン名・月額を見せる。カードの変更・解約・請求の履歴は、Stripe の画面へのボタン（T039）。
 * 申し込み直しは作り込み。
 * 開けない役割（生活相談員が URL を打ったなど）は、API が 403 を返すので、その文言を出す（FR-007）。
 */
export function Billing() {
  const billing = useQuery({
    queryKey: ['admin', 'billing'],
    queryFn: () => api.get<BillingInfo>('/api/admin/billing'),
    retry: false,
  })

  if (billing.isPending) return <Message k="layout.loading" />
  if (billing.isError) return <Message k={messageKeyOf(billing.error)} />
  return (
    <>
      <BillingView billing={billing.data} />
      {/* 初期データの施設は Stripe とつながっていないので、ボタンを出さない（R-05） */}
      {billing.data.can_manage && <PortalButton />}
    </>
  )
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ja-JP', {
    // ブラウザの時差で日がずれないように、日本時間で出す
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

/** 画面の中身（テストではこれを直接出す）。 */
export function BillingView({ billing }: { billing: BillingInfo }) {
  // 次に引き落とされるのは、契約中と支払いに失敗（Stripe が払い直しを試す）のときだけ
  const charges = billing.status === 'active' || billing.status === 'payment_failed'
  // 解約予定日は、解約予定のときだけ。Stripe が cancel_at を返さないときは、期間の終わり
  const lastDay =
    billing.status === 'cancel_scheduled' ? (billing.cancel_at ?? billing.current_period_end) : null
  return (
    <div className="space-y-6 p-4">
      <h1 className="text-xl font-bold">
        <Text k="billing.title" />
      </h1>
      {billing.status === 'payment_failed' && (
        <p role="alert" className="rounded border border-orange-700 bg-orange-50 p-3 text-sm">
          <Icon name="warning" className="mr-1" />
          <Text k="billing.payment_failed_note" />
        </p>
      )}
      <dl className="divide-y border-y">
        <Row labelKey="billing.status">
          <span className="font-bold">
            <Text k={`billing.state.${billing.status}`} />
          </span>
        </Row>
        <Row labelKey="billing.plan">
          {billing.plan_name} {billing.amount_jpy.toLocaleString('ja-JP')}{' '}
          <Text k="billing.per_month" />
        </Row>
        {billing.current_period_end && charges && (
          <Row labelKey="billing.period_end">{formatDate(billing.current_period_end)}</Row>
        )}
        {lastDay && <Row labelKey="billing.cancel_at">{formatDate(lastDay)}</Row>}
      </dl>
    </div>
  )
}

function Row({ labelKey, children }: { labelKey: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <dt className="text-gray-600">
        <Text k={labelKey} />
      </dt>
      <dd>{children}</dd>
    </div>
  )
}
