import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import i18n from '../../i18n'
import { stripRuby } from '../../i18n/rubyText'
import { MemoApprovalsView, ReasonForm } from './MemoApprovals'
import {
  isValidReason,
  jstDate,
  reasonLength,
  sortedWarnings,
  waitingHours,
  type Approval,
  type ApprovalTab,
} from './memoApprovalsView'

// ふりがな（<ruby>・<rt>・<rp>）を外して、画面に出る文字だけで比べる
function text(html: string): string {
  return html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')
}

const item = (changes: Partial<Approval> = {}): Approval => ({
  id: 1,
  resident_id: 10,
  resident_name: 'さくらさんの母',
  author_name: 'シティ',
  is_own: false,
  memo_date: '2026-10-28',
  written_at: '2026-10-28T03:00:00Z',
  source_lang: 'id',
  original_text: 'Hari ini beliau banyak tersenyum.',
  rewritten_text: '今日は、よく笑っていました。',
  back_translation: 'Hari ini beliau tersenyum banyak.',
  warnings: [],
  status: 'pending',
  confirmed_at: '2026-10-28T04:00:00Z',
  approved_at: null,
  waiting_minutes: 90,
  overdue: false,
  ...changes,
})

function render(
  items: Approval[] | null,
  props: {
    tab?: ApprovalTab
    listErrorKey?: string | null
    busyId?: number | null
    errorKey?: string | null
    errorId?: number | null
    doneAction?: 'approve' | 'return' | 'unpublish' | null
  } = {},
): string {
  return renderToStaticMarkup(
    <MemoApprovalsView
      tab={props.tab ?? 'pending'}
      onTab={() => {}}
      items={items}
      listErrorKey={props.listErrorKey ?? null}
      busyId={props.busyId ?? null}
      errorKey={props.errorKey ?? null}
      errorId={props.errorId ?? null}
      doneAction={props.doneAction ?? null}
      onAct={() => {}}
    />,
  )
}

describe('様子のメモの承認の画面（spec 007 の T023）', () => {
  it('入居者の呼び名・書いた職員・原文・整えた日本語・訳し戻しを並べて出す（FR-011）', () => {
    const shown = text(render([item()]))

    expect(shown).toContain('さくらさんの母')
    expect(shown).toContain('書いた職員：シティ')
    expect(shown).toContain('10月28日に書きました')
    expect(shown).toContain('原文（Bahasa Indonesia）')
    expect(shown).toContain('Hari ini beliau banyak tersenyum.')
    expect(shown).toContain('整えた日本語')
    expect(shown).toContain('今日は、よく笑っていました。')
    expect(shown).toContain('訳し戻し')
    expect(shown).toContain('Hari ini beliau tersenyum banyak.')
  })

  it('画面の上に急変・事故の案内、承認のそばに確かめる案内を出す（FR-016）', () => {
    const shown = text(render([item()]))

    expect(shown).toContain('急変・事故は、すぐに電話で連絡してください')
    expect(shown).toContain('ほかの入居者の名前が入っていないか確かめてください')
    expect(shown).toContain('医療・服薬・体調の判断が入っていないか確かめてください')
  })

  it('確かめてからの経過時間を出す。1 時間より短ければ「1 時間未満」', () => {
    expect(text(render([item({ waiting_minutes: 30 })]))).toContain('確かめてから 1 時間未満')
    expect(text(render([item({ waiting_minutes: 5 * 60 + 20 })]))).toContain('確かめてから 5 時間')
  })

  it('24 時間を過ぎたものは「1 日以上待っています」と目立たせる（FR-015）', () => {
    const html = render([item({ waiting_minutes: 26 * 60, overdue: true })])

    expect(text(html)).toContain('⚠️ 確かめてから 26 時間')
    expect(text(html)).toContain('1 日以上待っています')
    expect(text(render([item()]))).not.toContain('1 日以上待っています')
  })

  it('注意の印を、急ぎのものから並べて出す。知らない印は出さない（FR-016）', () => {
    const shown = text(
      render([
        item({ warnings: ['length_changed', 'unknown_mark', 'urgent_words', 'other_name'] }),
      ]),
    )

    expect(shown).toContain('注意の印')
    expect(shown.indexOf('急変・事故のことが')).toBeLessThan(shown.indexOf('ほかの入居者の呼び名'))
    expect(shown.indexOf('ほかの入居者の呼び名')).toBeLessThan(
      shown.indexOf('長さが、大きく違います'),
    )
    expect(shown).not.toContain('unknown_mark')
    // 印がなければ、欄ごと出さない
    expect(text(render([item()]))).not.toContain('注意の印')
  })

  it('ほかの人のメモには、「承認する」と「戻す」を出す', () => {
    const html = render([item()])

    expect(text(html)).toContain('承認する')
    expect(text(html)).toContain('戻す')
    expect(text(html)).not.toContain('ほかのリーダーの承認を待っています')
  })

  it('自分が書いたメモには、承認も戻すも出さず、ほかのリーダーを待つと出す（FR-011a）', () => {
    const html = render([item({ is_own: true })])

    expect(text(html)).toContain('ほかのリーダーの承認を待っています')
    expect(text(html)).not.toContain('承認する')
    // 押せるのは「承認待ち」「承認済み」の切り替えの 2 つだけ（メモには、押せるボタンがない）
    expect(html.match(/<button/g)).toHaveLength(2)
  })

  it('承認待ちがなければ、そのことを出す', () => {
    expect(text(render([]))).toContain('承認待ちのメモはありません')
    expect(text(render([], { tab: 'approved' }))).toContain('承認済みのメモはありません')
  })

  it('承認済みの一覧には、公開を取り下げるだけを置く（承認する・戻すは出さない）', () => {
    const html = render(
      [item({ status: 'approved', approved_at: '2026-10-28T06:00:00Z', waiting_minutes: null })],
      { tab: 'approved' },
    )
    const shown = text(html)

    expect(shown).toContain('公開を取り下げる')
    expect(shown).toContain('10月28日に承認しました')
    expect(shown).not.toContain('承認する')
    expect(shown).not.toContain('確かめてから')
    expect(shown).toContain('新しい順に 50 件まで出ます')
    // 本人が書いたメモでも、公開は取り下げられる
    expect(
      text(render([item({ status: 'approved', is_own: true })], { tab: 'approved' })),
    ).toContain('公開を取り下げる')
  })

  it('承認待ち・承認済みを切り替えるボタンは、選んでいる方を太字・色・押された状態で示す', () => {
    const html = render([], { tab: 'approved' })

    expect(html).toContain('aria-pressed="true"')
    expect(html).toContain('aria-pressed="false"')
    // 選んでいる方は、太字・色・押された状態（aria-pressed）で示す。✔・✓ などの印は付けない
    // （端末で見え方が変わり、選んだときにボタンの幅がずれるため）
    expect(html).not.toMatch(/[✔✓]/)
    expect(html).toContain('font-bold text-white')
  })

  it('読み込み中・エラーのときも、見出しと切り替えのボタンは出し、一覧の場所だけを置き換える', () => {
    for (const html of [render(null), render(null, { listErrorKey: 'error.not_logged_in' })]) {
      expect(text(html)).toContain('様子のメモの承認')
      expect(html.match(/aria-pressed/g)).toHaveLength(2)
    }
    expect(text(render(null))).toContain('読み込んでいます')
    expect(text(render(null, { listErrorKey: 'error.not_logged_in' }))).not.toContain(
      '読み込んでいます',
    )
    // 読み込み中は、前のタブのメモを残さない（別の状態のメモに合わないボタンが付かないように）
    expect(text(render(null, { tab: 'approved' }))).not.toContain('公開を取り下げる')
  })

  it('同じ名前のボタンが並ぶので、どのメモのボタンかを入居者の呼び名の見出しで説明する（1.3.1・4.1.3）', () => {
    const pending = render([item({ id: 7 })])
    expect(pending).toContain('id="memo-7"')
    // 「承認する」（ConfirmButton）と「戻す」の両方
    expect(pending.match(/aria-describedby="memo-7"/g)).toHaveLength(2)

    const approved = render([item({ id: 8, status: 'approved' })], { tab: 'approved' })
    expect(approved.match(/aria-describedby="memo-8"/g)).toHaveLength(1)
  })

  it('メモの文・名前は、タグもふりがなの書き方も解釈せず、文字のまま出す（FR-017）', () => {
    const html = render([
      item({
        original_text: '<script>alert(1)</script>',
        rewritten_text: '{太郎|たろう}さんは元気でした',
        resident_name: '田中{花子|はなこ}',
        author_name: '<b>職員</b>',
      }),
    ])

    expect(html).not.toContain('<script>')
    expect(html).not.toContain('<b>職員')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(text(html)).toContain('{太郎|たろう}さんは元気でした')
    expect(text(html)).toContain('田中{花子|はなこ}')
  })

  it('整えた日本語・訳し戻しがまだないメモも、画面が壊れない', () => {
    const shown = text(render([item({ rewritten_text: null, back_translation: null })]))

    expect(shown).toContain('整えた日本語はまだありません')
    expect(shown).toContain('訳し戻しはありません')
  })

  it('操作が終わったことと、できなかった理由を、読み上げにも伝える（4.1.3）', () => {
    const done = render([], { doneAction: 'approve' })
    const failed = render([item()], { errorKey: 'error.invalid_state' })

    expect(done).toContain('role="status"')
    expect(text(done)).toContain('承認しました')
    expect(failed).toContain('role="alert"')
    expect(text(failed)).toContain('いまの状態では、この操作はできません')
  })

  it('できなかった理由は、押したメモの中に出す（一覧が長くても、押した場所の近くで気づける）', () => {
    const items = [1, 2, 3].map((id) => item({ id, resident_name: `入居者${id}` }))

    const html = render(items, { errorKey: 'error.invalid_state', errorId: 3 })

    expect(html.match(/role="alert"/g)).toHaveLength(1)
    const [, ...cards] = html.split('<article')
    expect(cards.map((card) => card.includes('role="alert"'))).toEqual([false, false, true])
    expect(text(cards[2])).toContain('いまの状態では、この操作はできません')
  })

  it('押したメモが一覧から消えたとき（409 のあとの読み直し）は、画面の上に出す', () => {
    // ほかのリーダーが先に承認すると、読み直しで承認待ちの一覧から消える。理由まで消えないように
    const html = render([item({ id: 1 })], { errorKey: 'error.invalid_state', errorId: 99 })

    expect(html.match(/role="alert"/g)).toHaveLength(1)
    expect(html.split('<article')[0]).toContain('role="alert"')
  })

  it('⚠️ は、読み上げに入れない（意味は文に書いてある）', () => {
    const html = render([
      item({ overdue: true, waiting_minutes: 26 * 60, warnings: ['other_name'] }),
    ])

    expect(html).not.toMatch(/(?<!aria-hidden="true">)⚠️/)
    expect(html.match(/<span aria-hidden="true">⚠️ <\/span>/g)).toHaveLength(2)
  })

  it('操作している最中のメモのボタンは押せない', () => {
    const html = render([item()], { busyId: 1 })

    expect(html).toContain('disabled=""')
    expect(text(html)).toContain('承認しています')
  })

  it('「承認する」は、家族に見えるようになるので、2 回押して決める（ConfirmButton）', () => {
    const html = render([item()])

    // 初めは「承認する」だけ。確かめの文は、1 回押したあとに出る
    expect(text(html)).toContain('承認する')
    expect(text(html)).not.toContain('もう一度押すと承認します')
    expect(text(html)).not.toContain('やめる')
    // 確かめの文は、日本語・インドネシア語・英語のどれの辞書にもある
    // （日本語に戻る設定があるので、言語ごとの辞書そのものを引く）
    for (const language of ['ja', 'id', 'en']) {
      expect(
        i18n.getResource(language, 'translation', 'memo_approval.approve_confirm'),
      ).toBeTruthy()
    }
    expect(stripRuby(i18n.t('memo_approval.approve_confirm'))).toBe(
      'もう一度押すと承認します（家族に見えます）',
    )
  })

  it('押すボタンは、押せる大きさ（44px 以上）にしている', () => {
    expect(render([item()])).toContain('min-h-11')
  })
})

describe('理由の欄（戻す・公開を取り下げる。FR-013・FR-013a）', () => {
  const form = renderToStaticMarkup(
    <ReasonForm
      id="reason-1"
      labelKey="memo_approval.return_label"
      submitKey="memo_approval.return_submit"
      busyKey="memo_approval.returning"
      busy={false}
      onSubmit={() => {}}
      onCancel={() => {}}
    />,
  )

  it('ラベル付きの入力欄と文字数を出す。まだ書いていないときは送れない', () => {
    expect(text(form)).toContain('戻す理由（書いた職員の画面に出ます。200 文字まで）')
    expect(text(form)).toContain('0 / 200')
    expect(form).toContain('<textarea')
    expect(form).toContain('aria-describedby="reason-1-count"')
    expect(form).toContain('disabled=""')
    expect(text(form)).toContain('やめる')
  })

  it('理由は 1〜200 文字（前後の空白は数えない。絵文字も 1 文字）', () => {
    expect(isValidReason('')).toBe(false)
    expect(isValidReason('  \n ')).toBe(false)
    expect(isValidReason('あ')).toBe(true)
    expect(isValidReason('あ'.repeat(200))).toBe(true)
    expect(isValidReason('あ'.repeat(201))).toBe(false)
    expect(reasonLength('😀'.repeat(200))).toBe(200)
  })
})

describe('小さな部品', () => {
  it('経過時間は、時間の単位で数える', () => {
    expect(waitingHours(59)).toBe(0)
    expect(waitingHours(60)).toBe(1)
    expect(waitingHours(25 * 60 + 5)).toBe(25)
  })

  it('日時（UTC）を日本時間の日付にする', () => {
    expect(jstDate('2026-10-28T15:30:00Z')).toBe('2026-10-29')
  })

  it('注意の印は、決めた順に並べる', () => {
    expect(sortedWarnings(['length_changed', 'urgent_words'])).toEqual([
      'urgent_words',
      'length_changed',
    ])
  })
})

describe('辞書（memo_approval.*）', () => {
  const leaves = (value: unknown): string[] =>
    typeof value === 'string'
      ? [value]
      : Object.values((value ?? {}) as Record<string, unknown>).flatMap(leaves)
  const sentences = leaves(i18n.getResource('ja', 'translation', 'memo_approval'))

  it('日本語の文が辞書にある', () => {
    expect(sentences.length).toBeGreaterThan(20)
  })

  it('ふりがなのない漢字がない（職員の画面なので、すべての漢字にふりがなを付ける）', () => {
    for (const sentence of sentences) {
      const bare = sentence.replace(/\{[^{}|]+\|[^{}|]+\}/g, '').replace(/\{\{[^}]+\}\}/g, '')
      expect(bare, `ふりがなのない漢字がある：${sentence}`).not.toMatch(/[㐀-鿿]/)
    }
  })
})
