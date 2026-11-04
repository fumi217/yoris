import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import type { MessageRow } from '../staff/messagesView'
import type { StaffReservation } from '../staff/visitReservationRows'
import { AdminHomeView } from './AdminHome'
import { hiddenLabels } from './adminHomeView'
import type { Disclosure } from './DisclosureSettings'

const message = (overrides: Partial<MessageRow> = {}): MessageRow => ({
  id: 1,
  resident_id: 1,
  resident_display_name: '山田 花子',
  resident_display_name_ruby: '山田 花子',
  family_relationship: 'daughter',
  category: 'medical',
  assignee: null,
  summary: '食欲のこと',
  summary_ruby: '食欲のこと',
  status: 'waiting',
  handed_at: '2026-11-02T01:00:00Z',
  elapsed_days: 2,
  waiting_over_a_day: false,
  ...overrides,
})

const visit: StaffReservation = {
  id: 1,
  resident_id: 1,
  resident_name: '鈴木 一郎',
  resident_name_ruby: '鈴木 一郎',
  family_relationship: null,
  room: '205',
  visit_date: '2026-11-04',
  start_time: '14:00:00',
  party_size: 1,
  status: 'booked',
  cancel_reason: null,
  created_at: '2026-11-01T01:00:00Z',
}

const disclosure: Disclosure = {
  items: [
    { code: 'meal', visible: true },
    { code: 'sleep', visible: false },
  ],
  themes: [{ code: 'theme.daily_life', emoji: '', visible: true }],
  features: [{ code: 'album', visible: true }],
  related: [],
}

type Props = Parameters<typeof AdminHomeView>[0]
const render = (props: Partial<Props> = {}) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <AdminHomeView
        messageCount={1}
        messages={[message()]}
        visits={[visit]}
        memoCount={null}
        {...props}
      />
    </MemoryRouter>,
  )

const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('管理画面のトップ（今日の状況。#451）', () => {
  it('対応待ちのメッセージ・今日の面会の数の札を出し、押すとそれぞれの画面へ進む', () => {
    const html = render()

    expect(text(html)).toContain('今日の状況')
    expect(html).toContain('href="/admin/messages"')
    expect(html).toContain('href="/admin/visits"')
    expect(text(html)).toContain('次は 14:00')
  })

  it('1 日以上待っているメッセージがあれば、札を注意の色と文字で目立たせる', () => {
    const html = render({ messages: [message({ waiting_over_a_day: true })] })

    expect(text(html)).toContain('1 日以上待っているものがあります')
    expect(html).toContain('border-amber-300')
  })

  it('対応待ちのメッセージは、上から 3 件まで、詳細へのリンクで出す', () => {
    const many = [1, 2, 3, 4].map((id) => message({ id }))
    const html = render({ messages: many })

    expect(html).toContain('href="/admin/messages/3"')
    expect(html).not.toContain('href="/admin/messages/4"')
  })

  it('承認できない人には、メモの承認待ちの札を出さない', () => {
    expect(render({ memoCount: null })).not.toContain('/staff/memo-approvals')
    expect(render({ memoCount: 2 })).toContain('href="/staff/memo-approvals"')
  })

  it('開示設定を開けない人には、見せていない項目の札も一覧も出さない', () => {
    expect(render()).not.toContain('/admin/disclosure')
    const html = render({ disclosure })
    expect(html).toContain('href="/admin/disclosure"')
    expect(text(html)).toContain('眠り')
  })

  it('見せていない項目・テーマ・機能を、開示設定と同じ並びで集める', () => {
    expect(hiddenLabels(disclosure).map((label) => label.key)).toEqual(['disclosure.item.sleep'])
  })

  it('メッセージも面会もないときは、そう伝える', () => {
    const shown = text(render({ messageCount: 0, messages: [], visits: [] }))

    expect(shown).toContain('対応待ちのメッセージはありません')
    expect(shown).toContain('今日の予定はありません')
  })
})
