import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../api/client'
import '../../i18n'
import { RequestsView } from './Requests'
import {
  MAX_WAITING,
  remainingSlots,
  SendStopped,
  sendErrorKey,
  replyLinkFor,
  sentBeforeStop,
  sentThemeIdsBeforeStop,
  themeDescKey,
  themeIconName,
  toggleTheme,
  type FamilyRequest,
  type FamilyTheme,
} from './requestsView'

// 家族の「知りたいこと」の画面の刷新（#385）のテスト

const CODES = [
  'theme.daily_life',
  'theme.enjoying',
  'theme.residents',
  'theme.meals',
  'theme.staff',
  'theme.recreation',
  'theme.family_talk',
  'theme.supplies',
]
const themes: FamilyTheme[] = CODES.map((code, index) => ({ id: index + 1, code, emoji: '👀' }))

const request = (overrides: Partial<FamilyRequest> = {}): FamilyRequest => ({
  id: 1,
  theme_id: 1,
  theme_code: 'theme.daily_life',
  emoji: '👀',
  status: 'waiting',
  created_at: '2026-10-25T02:02:00Z',
  days_ago: 5,
  overdue: false,
  ...overrides,
})

const render = (props: Partial<Parameters<typeof RequestsView>[0]> = {}) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <RequestsView
        themes={themes}
        requests={[]}
        selected={[]}
        sending={false}
        cancelling={false}
        errorKey={null}
        sentCount={null}
        onToggle={vi.fn()}
        onSend={vi.fn()}
        onCancel={vi.fn()}
        {...props}
      />
    </MemoryRouter>,
  )

const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

// 送るボタン（aria-busy を持つ唯一のボタン）
const sendButton = (html: string) =>
  html.match(/<button[^>]*aria-busy[^>]*>.*?<\/button>/s)?.[0] ?? ''

describe('RequestsView の見た目', () => {
  it('見出しと説明を出す', () => {
    const shown = text(render())

    expect(shown).toContain('知りたいことを選んでください')
    expect(shown).toContain('気になることを施設にリクエストできます')
  })

  it('テーマ 8 つを、アイコン・名前・説明のカードで出す。絵文字は出さない', () => {
    const html = render()

    expect(html.match(/aria-pressed/g)).toHaveLength(8)
    expect(text(html)).toContain('日中どのように過ごしていますか？')
    expect(text(html)).toContain('足りないものがないか')
    expect(html).not.toContain('👀')
    expect(html).not.toMatch(/[\u{1F300}-\u{1FAFF}]/u)
  })

  it('2 列（スマホは 1 列）', () => {
    expect(render()).toContain('grid-cols-1 gap-3 sm:grid-cols-2')
  })

  it('選んでいるカードは、aria-pressed と、青いチェックの丸。選んでいないカードは空の丸', () => {
    const html = render({ selected: [2] })

    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1)
    expect(html).toContain('border-primary')
    // チェックの丸は 1 つ（選んだ 1 つだけ）
    expect(html.match(/data-icon="circle-check"/g)).toHaveLength(1)
  })

  it('目のアイコンは使わない', () => {
    expect(render({ requests: [request({ status: 'answered' })] })).not.toMatch(/data-icon="eye/)
  })

  it('送信エリア：選んでいないときは、押せない。「選んでいません」', () => {
    const html = render()

    expect(text(html)).toContain('選んでいません')
    expect(sendButton(html)).toContain('disabled=""')
    expect(text(sendButton(html))).toContain('この内容でリクエストを送る')
  })

  it('送信エリア：選んだ件数と、あと何件選べるかを出す。押せる', () => {
    const html = render({ selected: [1, 2] })

    expect(text(html)).toContain('2件選択中')
    expect(text(html)).toContain('あと1件まで選べます')
    expect(sendButton(html)).not.toContain('disabled=""')
  })

  it('空きの数まで選んだら、ほかの選んでいないカードは押せなくなる（選んだカードは外せる）', () => {
    const html = render({ selected: [1, 2, 3] })

    // 8 つのうち、選んだ 3 つ以外の 5 つが押せない
    expect(html.match(/<button[^>]*aria-pressed="false"[^>]*disabled=""/g)).toHaveLength(5)
    expect(html.match(/<button[^>]*aria-pressed="true"[^>]*disabled=""/g)).toBeNull()
  })

  it('返事待ちのテーマは、押せず、「返事待ち」の文字を添える。空きは、その分だけ減る', () => {
    const html = render({ requests: [request({ theme_id: 3, theme_code: 'theme.residents' })] })

    expect(html).toMatch(/<button[^>]*aria-pressed="false"[^>]*disabled=""/)
    expect(text(html)).toContain('返信待ち')
    expect(text(html)).toContain('あと2件まで選べます')
  })

  it('返事待ちが 3 件あるときは、送れない案内を出す', () => {
    const requests = [1, 2, 3].map((id) => request({ id, theme_id: id }))

    expect(text(render({ requests }))).toContain(
      '返信待ちが 3件あります。施設からの返信が届くと、またリクエストを送信することができます',
    )
  })

  it('送ったリクエスト：テーマ・状態・送った日時（◯日前）・状態の印', () => {
    const shown = text(
      render({
        requests: [
          request({ id: 1, status: 'answered' }),
          request({ id: 2, theme_id: 2, theme_code: 'theme.enjoying', status: 'waiting' }),
        ],
      }),
    )

    expect(shown).toContain('送ったリクエスト')
    expect(shown).toContain('返事が届きました')
    expect(shown).toContain('返信あり')
    expect(shown).toContain('返信待ち')
    expect(shown).toContain('10月25日 11:02')
    expect(shown).toContain('5日前')
  })

  it('送ったリクエストの丸アイコンは、状態によらず、いつもテーマのアイコン（状態は印だけで示す）', () => {
    const icon = (status: FamilyRequest['status']) =>
      render({ requests: [request({ status, theme_code: 'theme.meals' })] }).match(
        /<li class="flex flex-wrap items-start[\s\S]*?<svg[^>]*data-icon="([a-z-]+)"/,
      )?.[1]

    expect(icon('waiting')).toBe(icon('answered'))
    expect(icon('cancelled')).toBe(icon('answered'))
    expect(icon('answered')).toBe('utensils')
  })

  it('送信エリアはカードにしない（枠・影の箱にしない）', () => {
    const html = render({ selected: [1] })
    const area = html.slice(html.indexOf('border-t border-card-line'))

    expect(html).toContain('border-t border-card-line')
    expect(area.slice(0, 120)).not.toContain('shadow-sm')
  })

  it('回答済みは「連絡帳で見る」（リンク）、回答待ちは取り消しのボタン', () => {
    const answered = render({ requests: [request({ status: 'answered' })] })
    const waiting = render({ requests: [request({ status: 'waiting' })] })

    expect(answered).toMatch(/<a [^>]*href="\/family"/)
    expect(text(answered)).toContain('連絡帳で見る')
    expect(text(waiting)).toContain('取り消す')
    expect(text(answered)).not.toContain('取り消す')
  })

  it('3 日たっても返事がないときは、電話の案内を出す（FR-014）', () => {
    const shown = text(render({ requests: [request({ overdue: true })] }))

    expect(shown).toContain('お急ぎのときは、施設にお電話ください')
  })

  it('まだ送っていないときは、そう伝える', () => {
    expect(text(render())).toContain('まだ送ったリクエストはありません')
  })

  it('送れたときは件数を知らせ、途中で止まったときは、送れた件数と理由を知らせる', () => {
    const done = text(render({ sentCount: 2 }))
    const stopped = text(render({ sentCount: 1, errorKey: 'error.too_many_waiting' }))

    expect(done).toContain('2件のリクエストを送りました')
    expect(stopped).toContain('1件は送れましたが、残りは送れませんでした')
    expect(stopped).not.toContain('件のリクエストを送りました')
  })
})

describe('ようこさんの指摘への対応（#387）', () => {
  it('カードの高さをそろえる（2 列でも、行ごとに同じ高さ）', () => {
    const html = render()

    expect(html).toMatch(/<ul class="[^"]*auto-rows-fr[^"]*sm:grid-cols-2/)
    expect(html).toMatch(/<li class="flex">/)
  })

  it('押せないカード（返事待ち）は、グレーの背景・破線の枠で見せる。押せるカードは、白', () => {
    const waiting = render({ requests: [request({ theme_id: 1, status: 'waiting' })] })
    const first = waiting.match(/<button[^>]*>/g)?.[0] ?? ''
    const second = waiting.match(/<button[^>]*>/g)?.[1] ?? ''

    expect(first).toContain('disabled=""')
    expect(first).toContain('bg-page')
    expect(first).toContain('border-dashed')
    expect(first).not.toContain('bg-white')
    expect(second).toContain('bg-white')
    expect(second).not.toContain('border-dashed')
  })

  it('「回答」ではなく、受け取った側の言い方（返信あり・返信待ち）にする', () => {
    const shown = text(
      render({
        requests: [
          request({ id: 1, status: 'answered' }),
          request({ id: 2, status: 'waiting', theme_id: 2, theme_code: 'theme.meals' }),
        ],
      }),
    )

    expect(shown).toContain('返信あり')
    expect(shown).toContain('返信待ち')
    expect(shown).not.toContain('回答')
  })

  it('「取り消す」ボタンは、背景色と影のあるボタン', () => {
    const html = render({ requests: [request({ status: 'waiting' })] })
    const button = html.match(/<button[^>]*>(?=<span>(?:<ruby>)?取)/)?.[0] ?? ''

    expect(button).toContain('bg-page')
    expect(button).toContain('shadow-sm')
  })

  it('途中で止まったときは、送れたテーマの名前を出す。名前が分からないときは件数で出す', () => {
    const named = text(
      render({ sentCount: 1, sentThemeIds: [1], errorKey: 'error.too_many_waiting' }),
    )
    const two = text(
      render({ sentCount: 2, sentThemeIds: [1, 4], errorKey: 'error.too_many_waiting' }),
    )
    const unknown = text(render({ sentCount: 1, errorKey: 'error.too_many_waiting' }))

    expect(named).toContain('「普段の様子」は送れましたが、残りは送れませんでした')
    expect(two).toContain('「普段の様子」「食事の様子」は送れましたが、残りは送れませんでした')
    expect(unknown).toContain('1件は送れましたが、残りは送れませんでした')
  })

  it('途中で止まったときのエラーは、送れたテーマの id を持つ', () => {
    const stopped = new SendStopped(
      2,
      new ApiError(409, 'too_many_waiting', 'error.too_many_waiting'),
      [3, 5],
    )

    expect(sentThemeIdsBeforeStop(stopped)).toEqual([3, 5])
    expect(sentThemeIdsBeforeStop(new Error('x'))).toEqual([])
  })
})

describe('空きがないときの理由（#387 ようこさん）', () => {
  const waitingRequests = [1, 2, 3].map((id) =>
    request({
      id,
      theme_id: id,
      theme_code: `theme.${['daily_life', 'enjoying', 'residents'][id - 1]}`,
    }),
  )
  const note =
    '返信待ちが 3件あります。施設からの返信が届くと、またリクエストを送信することができます'

  it('空きがないときは、見出しのすぐ下に出す（カードより前）。下の送信エリアには、出さない', () => {
    const shown = text(render({ requests: waitingRequests }))

    expect(shown.match(new RegExp(note, 'g'))).toHaveLength(1)
    expect(shown.indexOf(note)).toBeLessThan(shown.indexOf('普段の様子'))
    expect(shown).not.toContain('あと')
  })

  it('空きがあるときは、出さない（下に「あと ◯ 件まで選べます」）', () => {
    const shown = text(render({ requests: waitingRequests.slice(0, 1) }))

    expect(shown).not.toContain(note)
    expect(shown).toContain('あと2件まで選べます')
  })
})

describe('テーマの選び方（FR-014）', () => {
  it('返事待ちは最大 3 件', () => {
    expect(MAX_WAITING).toBe(3)
  })

  it('空きの数は、3 件から返事待ちの件数を引いた数（返事済み・取り消しは数えない）', () => {
    expect(remainingSlots([])).toBe(3)
    expect(remainingSlots([request({ id: 1 }), request({ id: 2, theme_id: 2 })])).toBe(1)
    expect(
      remainingSlots([request({ status: 'answered' }), request({ id: 2, status: 'cancelled' })]),
    ).toBe(3)
    expect(remainingSlots([1, 2, 3, 4].map((id) => request({ id, theme_id: id })))).toBe(0)
  })

  it('選ぶ・外す。空きの数までしか選べない', () => {
    expect(toggleTheme([], 1, 3)).toEqual([1])
    expect(toggleTheme([1], 2, 3)).toEqual([1, 2])
    expect(toggleTheme([1, 2], 1, 3)).toEqual([2])
    expect(toggleTheme([1, 2, 3], 4, 3)).toEqual([1, 2, 3])
    expect(toggleTheme([1], 2, 1)).toEqual([1])
    expect(toggleTheme([], 1, 0)).toEqual([])
  })

  it('テーマごとにアイコンと説明がある（8 つとも）', () => {
    for (const code of CODES) {
      expect(themeIconName(code)).toMatch(/^theme-/)
      expect(themeDescKey(code)).toMatch(/^theme_desc\./)
    }
    expect(themeIconName('theme.unknown')).toBe('requests')
  })

  it('順に送る途中で止まったとき：送れた件数と、止めた理由（エラーの文言）が分かる', () => {
    const stopped = new SendStopped(
      1,
      new ApiError(409, 'too_many_waiting', 'error.too_many_waiting'),
    )

    expect(sentBeforeStop(stopped)).toBe(1)
    expect(sendErrorKey(stopped)).toBe('error.too_many_waiting')
    expect(sentBeforeStop(new Error('x'))).toBe(0)
  })
})

describe('「連絡帳で見る」の行き先（#403）', () => {
  it('返事が入った日の連絡帳へ。日付が分からないときは、今日の連絡帳', () => {
    expect(replyLinkFor({ reply_date: '2026-10-26' })).toBe('/family?date=2026-10-26')
    expect(replyLinkFor({ reply_date: null })).toBe('/family')
    expect(replyLinkFor({})).toBe('/family')
    // 形の合わない値は、使わない（アドレスに入れない）
    expect(replyLinkFor({ reply_date: '../admin' })).toBe('/family')
    expect(replyLinkFor({ reply_date: '2026-10-26&x=1' })).toBe('/family')
  })

  it('返事が届いたリクエストのリンクは、返事の日の連絡帳。返事待ちには、リンクを出さない', () => {
    const answered = render({
      requests: [request({ status: 'answered', reply_date: '2026-10-20' })],
    })
    const waiting = render({ requests: [request({ status: 'waiting' })] })

    expect(answered).toContain('href="/family?date=2026-10-20"')
    expect(waiting).not.toContain('href="/family')
  })
})
