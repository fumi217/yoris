import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import '../../i18n'
import { ApiError } from '../../api/client'
import { MemoEditorView } from './MemoEditor'
import {
  canConfirm,
  canWithdraw,
  errorKeyFor,
  isEditable,
  needsBackTranslation,
  originalChanged,
  rewrittenChanged,
  rewrittenProblem,
  REWRITTEN_MAX,
  statusKey,
  warningKeys,
  type Memo,
} from './memoEditorLogic'

// 様子のメモを書く画面の、訳し戻し・印・確かめました・取り下げる・戻された理由・一覧のテスト
// （spec 007 の 007-T019。FR-007〜010・FR-013・FR-016・FR-017）

const ORIGINAL = 'Hari ini Ibu kurang tersenyum dibanding biasanya, tapi makan siangnya habis.'
const REWRITTEN = '今日はいつもより笑顔が少なめでしたが、お昼ごはんは全部召し上がりました。'
const BACK = 'Hari ini senyumnya sedikit, tetapi makan siangnya habis.'

const memo = (overrides: Partial<Memo> = {}): Memo => ({
  id: 1,
  resident_id: 10,
  memo_date: '2026-10-27',
  written_at: '2026-10-27T03:00:00Z',
  source_lang: 'id',
  original_text: ORIGINAL,
  rewritten_text: null,
  back_translation: null,
  warnings: [],
  status: 'draft',
  return_reason: null,
  ...overrides,
})

const render = (props: Partial<Parameters<typeof MemoEditorView>[0]> = {}) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <MemoEditorView
        residentId="10"
        resident={{
          id: 10,
          display_name: 'さくらさんの母',
          display_name_ruby: 'さくらさんの母',
          room: '203',
        }}
        lang="id"
        onLang={vi.fn()}
        text=""
        onText={vi.fn()}
        memo={null}
        pending={false}
        errorKey={null}
        onSubmit={vi.fn()}
        {...props}
      />
    </MemoryRouter>,
  )

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const visibleText = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/&gt;/g, '>')
    .replace(/&lt;/g, '<')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')

/** ボタンを、属性と、画面に出る文字（ふりがなを除く）で取り出す。 */
const buttons = (html: string) =>
  [...html.matchAll(/<button([^>]*)>(.*?)<\/button>/gs)].map((found) => ({
    attrs: found[1],
    text: visibleText(found[2]),
  }))

/** 文言のボタン（見つからなければ undefined）。 */
const button = (html: string, label: string) =>
  buttons(html).find((item) => item.text.includes(label))

const ready = memo({ rewritten_text: REWRITTEN, back_translation: BACK })

describe('訳し戻し・印（FR-007・FR-016）', () => {
  it('インドネシア語・英語の職員には、原文・整えた日本語・訳し戻しを並べて出す（FR-007）', () => {
    const text = visibleText(render({ staffLanguage: 'id', memo: ready }))

    expect(text).toContain(ORIGINAL)
    expect(text).toContain(REWRITTEN)
    expect(text).toContain('訳し戻し')
    expect(text).toContain(BACK)
  })

  it('日本語の職員には、訳し戻しを出さない（FR-007）', () => {
    const text = visibleText(
      render({ staffLanguage: 'ja', memo: memo({ source_lang: 'ja', rewritten_text: REWRITTEN }) }),
    )

    expect(text).not.toContain('訳し戻し')
  })

  it('訳し戻しがまだないとき・直した文があるときは、訳し戻すよう案内し、古い訳し戻しを出さない', () => {
    const none = visibleText(
      render({ staffLanguage: 'id', memo: memo({ rewritten_text: REWRITTEN }) }),
    )
    const stale = visibleText(
      render({ staffLanguage: 'id', memo: ready, editedRewritten: REWRITTEN + '（直した）' }),
    )

    expect(none).toContain('訳し戻しがまだありません')
    expect(stale).toContain('訳し戻しがまだありません')
    expect(stale).not.toContain(BACK)
  })

  it('保存できたのに訳し戻しだけが空のとき、訳し戻しだけをやり直すボタンを出す（保存した日本語は消さない）', () => {
    const noBack = memo({ rewritten_text: REWRITTEN })
    const html = render({ staffLanguage: 'id', memo: noBack, onBackTranslate: vi.fn() })
    const retry = button(html, '直した文を訳し戻す')

    expect(retry).toBeDefined()
    expect(retry?.attrs).not.toContain('disabled=""')
    // 「もう一度日本語にする」（整え直し。直した文が消える）とは別のボタン
    expect(button(html, 'もう一度日本語にする')).toBeDefined()
    expect(button(html, 'もう一度日本語にする')?.text).not.toContain('訳し戻')
  })

  it('訳し戻しをやり直している間は、押せず、「訳し戻しています」と出る', () => {
    const html = render({
      staffLanguage: 'id',
      memo: memo({ rewritten_text: REWRITTEN }),
      onBackTranslate: vi.fn(),
      pending: true,
      action: 'back_translate',
    })

    expect(button(html, '訳し戻しています')?.attrs).toContain('disabled=""')
  })

  it('訳し戻しがすでにあるとき・日本語の職員・直せないメモ・直している途中は、やり直しのボタンを出さない', () => {
    const labels = (html: string) =>
      buttons(html).filter((item) => item.text.includes('直した文を訳し戻す')).length

    // 訳し戻しがある
    expect(labels(render({ staffLanguage: 'id', memo: ready, onBackTranslate: vi.fn() }))).toBe(0)
    // 日本語の職員は、訳し戻さない
    expect(
      labels(
        render({
          staffLanguage: 'ja',
          memo: memo({ source_lang: 'ja', rewritten_text: REWRITTEN }),
          onBackTranslate: vi.fn(),
        }),
      ),
    ).toBe(0)
    // 承認待ちなどの、直せないメモ
    expect(
      labels(
        render({
          staffLanguage: 'id',
          memo: memo({ status: 'pending', rewritten_text: REWRITTEN }),
          onBackTranslate: vi.fn(),
        }),
      ),
    ).toBe(0)
    // 直している途中は、上の「直した文を訳し戻す」（保存＋訳し戻し）の 1 つだけ
    expect(
      labels(
        render({
          staffLanguage: 'id',
          memo: memo({ rewritten_text: REWRITTEN }),
          editedRewritten: REWRITTEN + '（直した）',
          onSave: vi.fn(),
          onBackTranslate: vi.fn(),
        }),
      ),
    ).toBe(1)
  })

  it('訳し戻しは、文字のまま出す（タグ・ふりがなの書き方を解釈しない。FR-017）', () => {
    const html = render({
      staffLanguage: 'id',
      memo: memo({
        status: 'pending',
        rewritten_text: REWRITTEN,
        back_translation: '<script>alert(1)</script> {漢字|かんじ}',
      }),
    })

    expect(html).not.toContain('<script>')
    expect(visibleText(html)).toContain('<script>alert(1)</script> {漢字|かんじ}')
  })

  it('原文・整えた日本語も、読むだけの画面でも直す欄でも、文字のまま出す（T031。FR-017）', () => {
    const script = '<script>alert(1)</script>'
    const written = { original_text: script, rewritten_text: script, back_translation: BACK }

    for (const status of ['pending', 'draft'] as const) {
      const html = render({ staffLanguage: 'id', memo: memo({ ...written, status }) })

      expect(html, status).not.toContain('<script>')
      expect(html, status).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    }
    // 読むだけの画面では、原文が文字として見える
    const readOnly = render({ staffLanguage: 'id', memo: memo({ ...written, status: 'pending' }) })
    expect(visibleText(readOnly)).toContain(script)
  })

  it('注意の印を、急ぐものから並べて出す。知らない印は出さない。印は読み上げに入れない', () => {
    const html = render({
      staffLanguage: 'id',
      memo: memo({
        rewritten_text: REWRITTEN,
        back_translation: BACK,
        warnings: ['length_changed', 'unknown_code', 'medical_added', 'urgent_words'],
      }),
    })
    const text = visibleText(html)

    expect(text).toContain('注意急変・事故のような言葉があります')
    expect(text).not.toContain('注意の印')
    expect(html).toMatch(/<svg[^>]*data-icon="triangle-exclamation"[^>]*aria-hidden="true"/)
    const urgent = text.indexOf('急変・事故のような言葉があります')
    const medical = text.indexOf('原文にない医療・服薬・体調の言葉が')
    const length = text.indexOf('長さが大きく違います')
    expect(urgent).toBeGreaterThan(-1)
    expect(urgent).toBeLessThan(medical)
    expect(medical).toBeLessThan(length)
    expect(text).not.toContain('unknown_code')
    expect(visibleText(render({ memo: memo({ rewritten_text: REWRITTEN }) }))).not.toContain(
      '注意の印',
    )
  })
})

describe('確かめました・取り下げる・戻された理由（FR-008〜010・FR-013）', () => {
  it('訳し戻しまで済んだら、「確かめました」を押せる', () => {
    const html = render({ staffLanguage: 'id', memo: ready })

    expect(visibleText(html)).toContain('原文と訳し戻しが同じ意味か確かめてから、押してください')
    expect(button(html, '確かめました')?.attrs).not.toContain('disabled=""')
  })

  it('整えた日本語がまだない・訳し戻しがない・直した文を保存していないときは、押せない', () => {
    const notYet = render({ staffLanguage: 'id', memo: memo() })
    const noBack = render({ staffLanguage: 'id', memo: memo({ rewritten_text: REWRITTEN }) })
    const edited = render({
      staffLanguage: 'id',
      memo: ready,
      editedRewritten: REWRITTEN + '（直した）',
    })

    // 整えた日本語がないうちは、確かめる欄ごと出ない
    expect(button(notYet, '確かめました')).toBeUndefined()
    for (const html of [noBack, edited]) {
      expect(button(html, '確かめました')?.attrs).toContain('disabled=""')
      expect(visibleText(html)).toContain('直した文を訳し戻してから、確かめましょう')
    }
  })

  it('日本語の職員は、訳し戻しがなくても、整えた日本語があれば押せる', () => {
    const html = render({
      staffLanguage: 'ja',
      memo: memo({ source_lang: 'ja', rewritten_text: REWRITTEN }),
    })

    expect(button(html, '確かめました')?.attrs).not.toContain('disabled=""')
  })

  it('整えた日本語を直したら、直した文を訳し戻す（日本語の職員は、保存するだけ）', () => {
    const edited = (staffLanguage: string) =>
      visibleText(render({ staffLanguage, memo: ready, editedRewritten: REWRITTEN + '（直した）' }))

    expect(edited('id')).toContain('直した文を訳し戻す')
    expect(edited('ja')).toContain('直した文を保存する')
    // 直していないときは、出ない
    expect(visibleText(render({ staffLanguage: 'id', memo: ready }))).not.toContain(
      '直した文を訳し戻す',
    )
  })

  it('取り下げられるのは、下書き・承認待ち・戻されたメモだけ（FR-010）', () => {
    for (const status of ['draft', 'pending', 'returned'] as const) {
      const html = render({ memo: memo({ status, rewritten_text: REWRITTEN }) })
      expect(visibleText(html)).toContain('取り下げる')
    }
    for (const status of ['approved', 'withdrawn'] as const) {
      const html = render({ memo: memo({ status, rewritten_text: REWRITTEN }) })
      expect(visibleText(html)).not.toContain('取り下げる')
    }
    expect(visibleText(render())).not.toContain('取り下げる')
  })

  it('承認待ちは、確かめる欄を出さず、「承認を待っています」と出す', () => {
    const text = visibleText(
      render({ memo: memo({ status: 'pending', rewritten_text: REWRITTEN }) }),
    )

    expect(text).toContain('承認待ち')
    expect(text).toContain('承認を待っています。家族には、まだ見えません')
    expect(text).not.toContain('確かめました')
  })

  it('戻されたメモは、戻された理由を文字のまま出し、直してもう一度確かめられる（FR-013）', () => {
    const html = render({
      staffLanguage: 'id',
      memo: memo({
        status: 'returned',
        rewritten_text: REWRITTEN,
        back_translation: BACK,
        return_reason: '<b>名前が入っています</b> {確認|かくにん}',
      }),
    })
    const text = visibleText(html)

    expect(text).toContain('戻されました')
    expect(text).toContain('戻された理由')
    expect(text).toContain('<b>名前が入っています</b> {確認|かくにん}')
    expect(html).not.toContain('<b>名前')
    // 戻されたメモは、直せる
    expect(html.match(/<textarea/g)).toHaveLength(2)
    expect(button(html, '確かめました')?.attrs).not.toContain('disabled=""')
  })

  it('操作している最中は、どのボタンも押せず、その操作の文言になる', () => {
    const confirming = render({
      staffLanguage: 'id',
      memo: ready,
      pending: true,
      action: 'confirm',
    })
    const withdrawing = render({
      staffLanguage: 'id',
      memo: ready,
      pending: true,
      action: 'withdraw',
    })

    expect(visibleText(confirming)).toContain('送っています')
    expect(visibleText(withdrawing)).toContain('取り下げています')
    expect(button(confirming, '送っています')?.attrs).toContain('disabled=""')
  })
})

describe('この入居者について書いたメモの一覧', () => {
  const items = [
    memo({ id: 3, status: 'returned', original_text: '<i>戻された</i>', return_reason: '理由' }),
    memo({ id: 2, status: 'pending', original_text: '承認待ちのメモ' }),
    memo({ id: 1, status: 'approved', original_text: '承認されたメモ' }),
  ]

  it('状態・書いた日・原文を出し、押すと開く。原文は文字のまま出す（FR-017）', () => {
    const html = render({ mine: items })
    const text = visibleText(html)

    expect(text).toContain('この方について書いたメモ')
    expect(text).toContain('戻されました')
    expect(text).toContain('承認待ち')
    expect(text).toContain('承認されました')
    expect(text).toContain('2026-10-27')
    expect(text).toContain('<i>戻された</i>')
    expect(html).not.toContain('<i>戻された')
    expect(buttons(html).filter((item) => item.text === '開く')).toHaveLength(3)
  })

  it('いま開いているメモの「開く」は押せない。開いているときだけ「新しいメモを書く」が出る', () => {
    const open = render({ mine: items, memo: items[1] })
    const none = render({ mine: items })

    expect(open).toMatch(/<button type="button" disabled="" aria-pressed="true"/)
    expect(visibleText(open)).toContain('新しいメモを書く')
    expect(visibleText(none)).not.toContain('新しいメモを書く')
  })

  it('まだ書いていないときは、「まだありません」と出す', () => {
    expect(visibleText(render({ mine: [] }))).toContain('まだありません')
    expect(visibleText(render())).toContain('まだありません')
  })
})

describe('整えた日本語を直す欄の、文字数と直し方の文言（デザインの決めごと 1.4.1・3.3.1・3.3.3。#386）', () => {
  const ready = memo({ rewritten_text: REWRITTEN })

  it('直す欄に、文字数（n / 1000）がいつも出る', () => {
    expect(visibleText(render({ memo: ready }))).toContain(`${[...REWRITTEN].length} / 1000`)
  })

  it('空にすると、枠の色だけでなく、文字と印でも「空です」と出る', () => {
    const html = render({ memo: ready, editedRewritten: '  ' })

    expect(visibleText(html)).toContain('整えた日本語が空です')
    expect(html).toMatch(/<p role="alert"[^>]*>.*data-icon="triangle-exclamation"/)
    expect(visibleText(html)).toContain('0 / 1000')
  })

  it('1000 文字を超えると、直し方が文字で出る', () => {
    const html = render({ memo: ready, editedRewritten: 'あ'.repeat(REWRITTEN_MAX + 1) })

    expect(visibleText(html)).toContain('1000 文字までで直してください')
    expect(visibleText(html)).toContain('1001 / 1000')
  })

  it('直していない、または直して収まっているときは、案内を出さない', () => {
    expect(visibleText(render({ memo: ready }))).not.toContain('直してください')
    expect(visibleText(render({ memo: ready, editedRewritten: REWRITTEN + 'です' }))).not.toContain(
      '直してください',
    )
  })

  it('「書いた原文は保存しました」は、原文を直している途中は出さない', () => {
    expect(visibleText(render({ memo: ready }))).toContain('書いた原文は保存しました')
    expect(visibleText(render({ memo: ready, editedOriginal: ORIGINAL + '。' }))).not.toContain(
      '書いた原文は保存しました',
    )
  })
})

describe('memoEditorLogic.ts（T019）', () => {
  const same = { original: ORIGINAL, rewritten: REWRITTEN }

  it('直せる状態と、取り下げられる状態（backend と同じ）', () => {
    expect(isEditable('draft')).toBe(true)
    expect(isEditable('returned')).toBe(true)
    for (const status of ['pending', 'approved', 'withdrawn'] as const) {
      expect(isEditable(status)).toBe(false)
    }
    const withdrawable = (['draft', 'pending', 'returned', 'approved', 'withdrawn'] as const).map(
      canWithdraw,
    )
    expect(withdrawable).toEqual([true, true, true, false, false])
    expect(statusKey('draft')).toBe('memo.status.draft')
  })

  it('「確かめました」の条件は、backend の confirm と同じ（FR-009）', () => {
    expect(canConfirm(ready, 'id', same)).toBe(true)
    // 整えた日本語がない
    expect(canConfirm(memo(), 'id', same)).toBe(false)
    // 日本語以外の職員で、訳し戻しがない
    expect(canConfirm(memo({ rewritten_text: REWRITTEN }), 'id', same)).toBe(false)
    expect(canConfirm(memo({ rewritten_text: REWRITTEN }), 'ja', same)).toBe(true)
    // 直したのに保存していない文がある
    expect(canConfirm(ready, 'id', { ...same, rewritten: REWRITTEN + 'x' })).toBe(false)
    expect(canConfirm(ready, 'id', { ...same, original: ORIGINAL + 'x' })).toBe(false)
    // 承認待ち以降は、確かめられない
    expect(canConfirm({ ...ready, status: 'pending' }, 'id', same)).toBe(false)
  })

  it('確かめました・取り下げるが 409 で断られたら、共通の「いまの状態では、できません」を出す', () => {
    // ほかの職員が先に承認した・取り下げたなどで、backend が 409 invalid_state を返したとき
    const conflict = new ApiError(409, 'invalid_state', 'error.invalid_state')
    const unavailable = new ApiError(503, 'ai_unavailable', 'error.ai_unavailable')

    expect(errorKeyFor(conflict)).toBe('error.invalid_state')
    // 書く画面だけの文言は、AI につながらないときだけ
    expect(errorKeyFor(unavailable)).toBe('memo.unavailable')
    expect(visibleText(render({ memo: ready, errorKey: errorKeyFor(conflict) }))).toContain(
      'いまの状態では、この操作はできません',
    )
  })

  it('直したかは、前後の空白を数えずに比べる', () => {
    expect(originalChanged(ready, `  ${ORIGINAL}\n`)).toBe(false)
    expect(originalChanged(ready, ORIGINAL + '。')).toBe(true)
    expect(rewrittenChanged(ready, ` ${REWRITTEN} `)).toBe(false)
    expect(rewrittenChanged(memo(), '')).toBe(false)
  })

  it('整えた日本語は、1〜1000 文字（backend と同じ）', () => {
    expect(rewrittenProblem('')).toBe('empty')
    expect(rewrittenProblem(' \n ')).toBe('empty')
    expect(rewrittenProblem('あ'.repeat(REWRITTEN_MAX))).toBeNull()
    expect(rewrittenProblem('あ'.repeat(REWRITTEN_MAX + 1))).toBe('too_long')
  })

  it('日本語の職員は訳し戻さない。印は決めた順に並べ、知らない印は出さない', () => {
    expect(needsBackTranslation('ja')).toBe(false)
    expect(needsBackTranslation('id')).toBe(true)
    expect(needsBackTranslation(undefined)).toBe(true)
    expect(warningKeys(['other_name', 'x', 'urgent_words'])).toEqual([
      'memo.warning.urgent_words',
      'memo.warning.other_name',
    ])
  })
})
