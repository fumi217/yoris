import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { adminMenuFor } from './adminMenu'
import { BillingView, type BillingInfo } from './Billing'

// ふりがな（<rt>・<rp>）と、そのほかのタグを外した、画面の文字だけ
const textOf = (html: string) =>
  html.replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '').replace(/<[^>]*>/g, '')

const billing: BillingInfo = {
  status: 'active',
  plan_name: '月額プラン',
  amount_jpy: 10000,
  current_period_end: '2026-11-26T00:00:00Z',
  cancel_at: null,
  can_subscribe: false,
  can_manage: true,
}

const render = (changes: Partial<BillingInfo> = {}) =>
  textOf(renderToStaticMarkup(<BillingView billing={{ ...billing, ...changes }} />))

describe('adminMenu（利用料）', () => {
  it('利用料のお支払いは、施設長・事務員にだけ出す', () => {
    expect(adminMenuFor('director').map((item) => item.to)).toContain('/admin/billing')
    expect(adminMenuFor('clerk').map((item) => item.to)).toContain('/admin/billing')
    expect(adminMenuFor('counselor').map((item) => item.to)).not.toContain('/admin/billing')
    expect(adminMenuFor(null)).toEqual([])
  })
})

describe('BillingView', () => {
  it('契約の状態とプラン名・月額を出す', () => {
    const html = render()

    expect(html).toContain('契約中')
    expect(html).toContain('月額プラン')
    expect(html).toContain('10,000')
    expect(html).toContain('次の請求日')
  })

  it('状態ごとの文言を出す', () => {
    expect(render({ status: 'payment_failed' })).toContain('失敗しました')
    expect(render({ status: 'cancel_scheduled', cancel_at: '2026-12-01T00:00:00Z' })).toContain(
      '解約予定日',
    )
    expect(render({ status: 'canceled' })).toContain('解約済み')
  })

  it('解約済みでは、次の請求日を出さない', () => {
    expect(render({ status: 'canceled' })).not.toContain('次の請求日')
  })

  it('支払いに失敗したら、カードを確かめる案内を警告として出す（US2 のシナリオ 2）', () => {
    const html = renderToStaticMarkup(
      <BillingView billing={{ ...billing, status: 'payment_failed' }} />,
    )

    expect(html).toContain('role="alert"')
    expect(textOf(html)).toContain('カードの有効期限などを確かめてください')
    expect(textOf(html)).toContain('次の請求日')
    expect(render()).not.toContain('カードの有効期限')
  })

  it('解約予定では、次の請求日の代わりに解約予定日を出す', () => {
    const html = render({ status: 'cancel_scheduled', cancel_at: '2026-11-25T16:00:00Z' })

    expect(html).not.toContain('次の請求日')
    expect(html).toContain('解約予定日')
    expect(html).toContain('2026年11月26日')
  })

  it('解約予定でなければ、cancel_at が残っていても解約予定日を出さない', () => {
    for (const status of ['active', 'payment_failed', 'canceled'] as const) {
      expect(render({ status, cancel_at: '2026-12-01T00:00:00Z' })).not.toContain('解約予定日')
    }
  })

  it('解約予定で cancel_at がなければ、期間の終わりを解約予定日にする', () => {
    const html = render({ status: 'cancel_scheduled', cancel_at: null })

    expect(html).toContain('解約予定日')
    expect(html).toContain('2026年11月26日')
  })

  it('日付は日本時間で出す（UTC の夜は、日本では翌日）', () => {
    const html = render({ current_period_end: '2026-11-25T16:00:00Z' })

    expect(html).toContain('2026年11月26日')
  })

  it('初期データの施設（次の請求日がない）でも出せる', () => {
    const html = render({ current_period_end: null, can_manage: false })

    expect(html).toContain('契約中')
    expect(html).not.toContain('次の請求日')
  })
})
