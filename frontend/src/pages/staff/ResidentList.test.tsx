import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { ResidentTable } from './ResidentList'
import {
  mealMarks,
  monthDay,
  totalWaitingMessages,
  visibleRows,
  type ResidentRow,
} from './residentRows'

const row = (overrides: Partial<ResidentRow> = {}): ResidentRow => ({
  id: 1,
  display_name: '佐藤さんの母',
  room: '101',
  meals: { breakfast: true, lunch: false, dinner: false, snack: false },
  mood: true,
  sleep: false,
  waiting_requests: 0,
  waiting_messages: 0,
  change_flag: null,
  ...overrides,
})

const render = (residents: ResidentRow[], unconfirmedFlagCount = 0) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ResidentTable
        data={{ date: '2026-10-26', residents, unconfirmed_flag_count: unconfirmedFlagCount }}
      />
    </MemoryRouter>,
  )

describe('residentList', () => {
  it('食事は朝・昼・夜・おやつの順に、記録済みかを並べる', () => {
    expect(mealMarks(row())).toEqual([
      { labelKey: 'record.slot.breakfast', recorded: true, optional: false },
      { labelKey: 'record.slot.lunch', recorded: false, optional: false },
      { labelKey: 'record.slot.dinner', recorded: false, optional: false },
      { labelKey: 'record.slot.snack', recorded: false, optional: true },
    ])
  })

  it('家族からのメッセージは、全員分を合計する', () => {
    expect(totalWaitingMessages([row({ waiting_messages: 2 }), row({ waiting_messages: 1 })])).toBe(
      3,
    )
  })

  it('日付は文字のまま月と日に分ける（タイムゾーンでずれない）', () => {
    expect(monthDay('2026-10-01')).toEqual({ month: 10, day: 1 })
  })
})

describe('ResidentTable', () => {
  it('入居者を押すと、その人の記録の画面へ進む', () => {
    const html = render([row({ id: 7 })])

    expect(html).toContain('href="/staff/residents/7"')
    expect(html).toContain('101')
    expect(html).toContain('佐藤さんの母')
  })

  it('朝・昼・夜のまだは目立たせ、おやつのまだは目立たせない', () => {
    const html = render([
      row({ meals: { breakfast: true, lunch: true, dinner: false, snack: false } }),
    ])

    // 目立たせるのは夜ごはんだけ（おやつは毎日付けるとは限らない）
    expect(html.match(/text-orange-700/g)).toHaveLength(2) // 夜・眠り
  })

  it('未記録は読み上げでも分かる', () => {
    const html = render([row()])

    expect(html).toContain('記録済み')
    expect(html).toContain('まだ記録していません')
  })

  it('返事待ち・家族からのメッセージは、あるときだけ件数を出す', () => {
    expect(render([row()])).not.toContain('💬')

    const html = render([row({ waiting_requests: 2, waiting_messages: 1 })])
    expect(html).toContain('返事待ちのリクエスト：2件')
    expect(html).toContain('家族からのメッセージ：1件')
  })

  it('入居者の呼び名は、HTML として解釈しない', () => {
    const html = render([row({ display_name: '<b>テスト</b>' })])

    expect(html).not.toContain('<b>テスト</b>')
    expect(html).toContain('&lt;b&gt;テスト&lt;/b&gt;')
  })

  it('入居者がいなければ、そう伝える', () => {
    expect(render([])).toContain('いません')
  })

  it('📩 の件数から、その入居者の家族からのメッセージの一覧へ進む', () => {
    const html = render([row({ id: 7, waiting_messages: 2 })])

    expect(html).toContain('href="/staff/messages?resident_id=7"')
    // リンクの中にリンクを入れない（記録の画面へのリンクとは別に並べる）
    expect(html).not.toMatch(/<a[^>]*>(?:(?!<\/a>).)*<a /)
  })

  it('📩 がなければ、メッセージへのリンクは出さない', () => {
    expect(render([row({ waiting_messages: 0 })])).not.toContain('resident_id=')
  })
})

describe('変化の目印（spec 006 の 006-T015）', () => {
  const unconfirmed = { has_flag: true, has_unconfirmed: true }
  const confirmed = { has_flag: true, has_unconfirmed: false }
  const rows = [
    row({ id: 1 }),
    row({ id: 2, change_flag: confirmed }),
    row({ id: 3 }),
    row({ id: 4, change_flag: unconfirmed }),
  ]

  it('目印の付いた入居者を先に。その中も、ほかの入居者も、入居の順のまま', () => {
    expect(visibleRows(rows, false).map((r) => r.id)).toEqual([2, 4, 1, 3])
  })

  it('絞ると、まだ確かめていない目印のある入居者だけ（確かめ済みは出さない）', () => {
    expect(visibleRows(rows, true).map((r) => r.id)).toEqual([4])
  })

  it('一覧の上に「確かめていない目印：◯件」を出す', () => {
    const html = render(rows, 1)

    expect(html).toContain('aria-pressed="false"')
    expect(html).toMatch(/<button[^>]*aria-pressed[^>]*>[\s\S]*?1[\s\S]*?<\/button>/)
  })

  it('目印のある行は、呼び名のすぐ横に「⚠️ いつもと違う様子」を出し、上に並べる', () => {
    const html = render([
      row({ id: 1, display_name: '目印なしさん' }),
      row({ id: 2, display_name: '目印ありさん', change_flag: unconfirmed }),
    ])

    expect(html.indexOf('目印ありさん')).toBeLessThan(html.indexOf('目印なしさん'))
    const flagged = html.slice(html.indexOf('目印ありさん'), html.indexOf('目印なしさん'))
    expect(flagged).toContain('⚠️')
    expect(html.slice(html.indexOf('目印なしさん'))).not.toContain('⚠️')
  })
})
