import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { adminMenuFor } from '../admin/adminMenu'
import { ResidentTable } from './ResidentList'
import { TodayVisitsView } from './TodayVisits'
import { CancelForm, VisitListView } from './VisitReservations'
import {
  bookedCount,
  groupByDate,
  listRange,
  visitsBase,
  type StaffReservation,
} from './visitReservationRows'

const reservation = (overrides: Partial<StaffReservation> = {}): StaffReservation => ({
  id: 1,
  visit_date: '2026-10-28',
  start_time: '10:00:00',
  resident_id: 3,
  resident_name: '佐藤さんの母',
  room: '101',
  party_size: 2,
  status: 'booked',
  created_at: '2026-10-26T01:05:00Z',
  cancel_reason: null,
  ...overrides,
})

const renderList = (rows: StaffReservation[], cancellingId: number | null = null) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <VisitListView rows={rows} cancellingId={cancellingId} onCancel={() => {}} />
    </MemoryRouter>,
  )

describe('visitReservationRows', () => {
  it('一覧は、今日から 4 週間先まで（API の上限 31 日に収まる）を読む', () => {
    expect(listRange('2026-10-27')).toEqual({ from: '2026-10-27', to: '2026-11-24' })
  })

  it('日付ごとにまとめ、並びは変えない', () => {
    const rows = [
      reservation({ id: 1 }),
      reservation({ id: 2, start_time: '13:00:00' }),
      reservation({ id: 3, visit_date: '2026-10-30' }),
    ]

    expect(groupByDate(rows).map((g) => [g.date, g.rows.map((r) => r.id)])).toEqual([
      ['2026-10-28', [1, 2]],
      ['2026-10-30', [3]],
    ])
  })

  it('今日の面会の組数は、予約済みだけを数える', () => {
    expect(
      bookedCount([reservation(), reservation({ id: 2, status: 'cancelled_by_family' })]),
    ).toBe(1)
  })

  it('開いた側（職員の画面・管理画面）を URL から決める', () => {
    expect(visitsBase('/staff/visits')).toBe('/staff/visits')
    expect(visitsBase('/admin/visits')).toBe('/admin/visits')
  })

  it('管理画面のトップには、事務員・生活相談員・施設長に出す（介護職員・リーダーは職員の画面から）', () => {
    for (const role of ['clerk', 'counselor', 'director'] as const) {
      expect(adminMenuFor(role).map((item) => item.to)).toContain('/admin/visits')
    }
  })
})

describe('VisitListView', () => {
  it('予約がなければ、そう伝える', () => {
    expect(renderList([])).toContain('ありません')
  })

  it('日付ごとに、時刻・居室・呼び名・人数・状態・予約した日時を出す', () => {
    const html = renderList([reservation()])

    expect(html).toContain('（水）')
    expect(html).toContain('10:00〜11:30')
    expect(html).toContain('101')
    expect(html).toContain('佐藤さんの母')
    // 予約した日時は日本時間（01:05Z → 10:05）
    expect(html).toContain('10/26 10:05')
    // 人数は、入居者の人数に見えないよう「来館者」と付ける（#311）
    expect(html).toMatch(/来館者.*2/)
  })

  it('予約済みにだけ「取り消す」を出す。施設が取り消した理由は文字としてだけ出す', () => {
    const html = renderList([
      reservation({ id: 1 }),
      reservation({
        id: 2,
        status: 'cancelled_by_staff',
        cancel_reason: '<b>感染症のため</b>',
      }),
    ])

    expect(html.match(/<button/g)).toHaveLength(1)
    expect(html).toContain('&lt;b&gt;感染症のため&lt;/b&gt;')
    expect(html).not.toContain('<b>感染症')
  })

  it('取り消している間は、ほかの予約の「取り消す」も押せない', () => {
    const html = renderList([reservation({ id: 1 }), reservation({ id: 2 })], 1)

    expect(html.match(/<button[^>]*disabled=""/g)).toHaveLength(2)
  })
})

describe('CancelForm', () => {
  it('理由の欄と、家族に届くことの案内を出す。理由が空なら取り消せない', () => {
    const html = renderToStaticMarkup(
      <CancelForm busy={false} disabled={false} onConfirm={() => {}} onStop={() => {}} />,
    )

    expect(html).toContain('<textarea')
    expect(html).toContain('メール')
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>.*?取/)
  })

  it('理由は、押す前は直せて、取り消している最中は直せない（読み取り専用。#317）', () => {
    const render = (busy: boolean) =>
      renderToStaticMarkup(
        <CancelForm busy={busy} disabled={false} onConfirm={() => {}} onStop={() => {}} />,
      )

    expect(render(false)).not.toMatch(/readonly/i)
    expect(render(true)).toMatch(/<textarea[^>]*readonly=""/i)
  })
})

describe('TodayVisitsView', () => {
  it('今日の予定がなければ、そう伝える', () => {
    expect(renderToStaticMarkup(<TodayVisitsView rows={[]} />)).toContain('ありません')
  })

  it('時刻・居室・呼び名・人数を出す', () => {
    const html = renderToStaticMarkup(
      <TodayVisitsView rows={[reservation({ start_time: '13:30:00' })]} />,
    )

    expect(html).toContain('13:30〜15:00')
    expect(html).toContain('佐藤さんの母')
    expect(html).toMatch(/来館者.*2/)
  })
})

describe('ResidentTable の「今日の面会」', () => {
  const render = (todayVisits: number | null) =>
    renderToStaticMarkup(
      <MemoryRouter>
        <ResidentTable
          data={{ date: '2026-10-27', residents: [], unconfirmed_flag_count: 0 }}
          todayVisits={todayVisits}
        />
      </MemoryRouter>,
    )

  it('組数を出し、今日の面会予定へ進む（0 組でも出す）', () => {
    expect(render(2)).toContain('href="/staff/visits/today"')
    expect(render(0)).toContain('href="/staff/visits/today"')
  })

  it('読めていないときは出さない', () => {
    expect(render(null)).not.toContain('/staff/visits/today')
  })
})
