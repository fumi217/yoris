import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { APPROVALS_KEY } from './memoApprovalsView'
import { ResidentList, ResidentTable } from './ResidentList'
import {
  mealMarks,
  monthDay,
  recordProgress,
  showCautionSection,
  splitByFlag,
  totalWaitingMessages,
  visibleRows,
  type ResidentListResponse,
  type ResidentRow,
} from './residentRows'

const row = (overrides: Partial<ResidentRow> = {}): ResidentRow => ({
  id: 1,
  display_name: '佐藤 文江',
  display_name_ruby: '佐藤 文江',
  room: '101',
  meals: { breakfast: true, lunch: false, dinner: false, snack: false },
  mood: true,
  sleep: false,
  waiting_requests: 0,
  waiting_messages: 0,
  change_flag: null,
  ...overrides,
})

const render = (
  residents: ResidentRow[],
  unconfirmedFlagCount = 0,
  memoApprovals: number | null = null,
) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ResidentTable
        data={{ date: '2026-10-26', residents, unconfirmed_flag_count: unconfirmedFlagCount }}
        memoApprovals={memoApprovals}
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
    expect(html).toContain('佐藤 文江')
  })

  it('記録のチップ：記録済みは緑と ✔、まだは点線と －。色だけに頼らない', () => {
    const html = render([
      row({ meals: { breakfast: true, lunch: true, dinner: false, snack: false } }),
    ])

    // 朝・昼・機嫌は記録済み（✔）、夜・眠りはまだ（－）。おやつは記録がないので、チップを出さない
    expect(html.match(/data-icon="check"/g)).toHaveLength(3)
    expect(html.match(/data-icon="minus"/g)).toHaveLength(2)
    expect(html.match(/border-dashed/g)).toHaveLength(2)
    expect(html).not.toContain('おやつ')
  })

  it('おやつは、記録があるときだけチップを出す', () => {
    const html = render([
      row({ meals: { breakfast: true, lunch: true, dinner: true, snack: true } }),
    ])

    expect(html).toContain('おやつ')
  })

  it('未記録は読み上げでも分かる', () => {
    const html = render([row()])

    expect(html).toContain('記録済み')
    expect(html).toContain('まだ記録していません')
  })

  it('返事待ち・家族からのメッセージは、あるときだけ件数を出す', () => {
    expect(render([row()])).not.toContain('data-icon="comment-dots"')

    const html = render([row({ waiting_requests: 2, waiting_messages: 1 })])
    expect(html).toContain('返事待ちのリクエスト：2件')
    expect(html).toContain('家族からのメッセージ：1件')
  })

  it('入居者の呼び名は、HTML として解釈しない', () => {
    const html = render([
      row({ display_name: '<b>テスト</b>', display_name_ruby: '<b>テスト</b>' }),
    ])

    expect(html).not.toContain('<b>テスト</b>')
    expect(html).toContain('&lt;b&gt;テスト&lt;/b&gt;')
  })

  it('入居者がいなければ、そう伝える', () => {
    expect(render([])).toContain('いません')
  })

  it('メッセージのアイコンの件数から、その入居者の家族からのメッセージの一覧へ進む', () => {
    const html = render([row({ id: 7, waiting_messages: 2 })])

    expect(html).toContain('href="/staff/messages?resident_id=7"')
    // リンクの中にリンクを入れない（記録の画面へのリンクとは別に並べる）
    expect(html).not.toMatch(/<a[^>]*>(?:(?!<\/a>).)*<a /)
  })

  it('メッセージがなければ、メッセージへのリンクは出さない', () => {
    expect(render([row({ waiting_messages: 0 })])).not.toContain('resident_id=')
  })
})

describe('今日の進み具合・気をつけたい人（#431）', () => {
  const flagged = { has_flag: true, has_unconfirmed: true }

  it('朝・昼・夜・機嫌・眠りの記録した欄を数える（おやつは数えない）', () => {
    const rows = [
      row({
        meals: { breakfast: true, lunch: true, dinner: true, snack: true },
        mood: true,
        sleep: true,
      }),
      row({
        id: 2,
        meals: { breakfast: false, lunch: false, dinner: false, snack: true },
        mood: false,
        sleep: false,
      }),
    ]

    expect(recordProgress(rows)).toEqual({ recorded: 5, total: 10 })
  })

  it('進み具合を文字と棒（progressbar）で出す', () => {
    const html = render([row()])

    expect(html).toContain('role="progressbar"')
    expect(html).toContain('aria-valuenow="2"')
    expect(html).toContain('aria-valuemax="5"')
    expect(html).toContain('2 / 5')
  })

  it('目印のある入居者は「気をつけたい人」に、ほかは「入居者のみなさん」にまとめる', () => {
    const rows = [row({ id: 1 }), row({ id: 2, change_flag: flagged })]

    const { caution, others } = splitByFlag(rows)
    expect(caution.map((r) => r.id)).toEqual([2])
    expect(others.map((r) => r.id)).toEqual([1])
    // ふりがなを外して、画面に出る文字で比べる
    const text = render(rows, 1).replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>|<\/?ruby>/g, '')
    expect(text).toContain('気をつけたい人')
    expect(text).toContain('入居者のみなさん')
  })

  it('目印がだれにもいないときは、「気をつけたい人」の面を出さない', () => {
    expect(render([row()]).replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>|<\/?ruby>/g, '')).not.toContain(
      '気をつけたい人',
    )
  })

  it('絞り込み中は、目印が 0 件になっても「気をつけたい人」の面を残す（戻すボタンを消さない）', () => {
    expect(showCautionSection(0, 0, false)).toBe(false)
    expect(showCautionSection(1, 0, false)).toBe(true)
    expect(showCautionSection(0, 2, false)).toBe(true)
    expect(showCautionSection(0, 0, true)).toBe(true)
  })

  it('家族からのメッセージの件数のリンクを出す', () => {
    const html = render([row({ waiting_messages: 2 })])

    expect(html).toContain('href="/staff/messages"')
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

  it('目印のある行は、呼び名のすぐ横に「いつもと違う様子」（注意のアイコン付き）を出し、上に並べる', () => {
    const html = render([
      row({ id: 1, display_name: '目印なし太郎', display_name_ruby: '目印なし太郎' }),
      row({
        id: 2,
        display_name: '目印あり太郎',
        display_name_ruby: '目印あり太郎',
        change_flag: unconfirmed,
      }),
    ])

    expect(html.indexOf('目印あり太郎')).toBeLessThan(html.indexOf('目印なし太郎'))
    const flagged = html.slice(html.indexOf('目印あり太郎'), html.indexOf('目印なし太郎'))
    expect(flagged).toContain('data-icon="triangle-exclamation"')
    expect(html.slice(html.indexOf('目印なし太郎'))).not.toContain(
      'data-icon="triangle-exclamation"',
    )
  })
})

// ふりがなのタグ（ruby・rt・rp）と、そのほかのタグを除いた、画面に見える文字
const visibleText = (html: string) =>
  html.replace(/<rp>.*?<\/rp>|<rt>.*?<\/rt>/g, '').replace(/<[^>]+>/g, '')

describe('様子のメモの承認待ち（spec 007 の 007-T028・FR-015）', () => {
  it('件数があるとき、承認の画面への入り口（今日のまとめのカード）と件数を出す', () => {
    const html = render([row()], 0, 3)

    expect(html).toContain('href="/staff/memo-approvals"')
    expect(visibleText(html)).toContain('様子のメモの承認待ち3件')
  })

  it('0 件でも入り口は出す', () => {
    expect(visibleText(render([row()], 0, 0))).toContain('様子のメモの承認待ち0件')
  })

  it('承認できない人・読めないとき（null）は、出さない', () => {
    const html = render([row()], 0, null)

    expect(html).not.toContain('memo-approvals')
    expect(visibleText(html)).not.toContain('承認待ち')
  })

  it('入り口は、通知・音・画面を遮る表示を出さない（カードのほかに、何も増えない）', () => {
    const without = render([row()], 0, null)
    const withEntry = render([row()], 0, 5)

    // 入り口のリンクだけを取り除くと、出さないときの画面と同じになる
    const linkOnly = /<a [^>]*href="\/staff\/memo-approvals"[^>]*>.*?<\/a>/
    expect(withEntry).toMatch(linkOnly)
    expect(withEntry.replace(linkOnly, '')).toBe(without)
  })
})

describe('ResidentList が、承認待ちの件数を入り口へ渡す（007-T028）', () => {
  // 読み込み済みの値を入れた QueryClient で描く（通信はしない。StaffHeader.test.tsx と同じ形）
  const renderList = (memoCount: { count: number | null } | undefined) => {
    const queryClient = new QueryClient()
    const residents: ResidentListResponse = {
      date: '2026-10-26',
      residents: [row()],
      unconfirmed_flag_count: 0,
    }
    queryClient.setQueryData(['staff', 'residents'], residents)
    if (memoCount) queryClient.setQueryData([...APPROVALS_KEY, 'count'], memoCount)
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ResidentList />
        </MemoryRouter>
      </QueryClientProvider>,
    )
  }

  it('API の件数を、入り口に出す', () => {
    const html = renderList({ count: 4 })

    expect(html).toContain('href="/staff/memo-approvals"')
    expect(visibleText(html)).toContain('様子のメモの承認待ち4件')
  })

  it('API が 0 件を返したときは、0 件で出す', () => {
    expect(visibleText(renderList({ count: 0 }))).toContain('様子のメモの承認待ち0件')
  })

  it('承認できない人（API が count: null）は、出さない。一覧は使える', () => {
    const html = renderList({ count: null })

    expect(html).not.toContain('memo-approvals')
    expect(visibleText(html)).toContain('101')
  })

  it('まだ読めていない・読めなかったとき（値がない）は、出さない。一覧は使える', () => {
    const html = renderList(undefined)

    expect(html).not.toContain('memo-approvals')
    expect(visibleText(html)).toContain('101')
  })
})
