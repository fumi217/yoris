import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { ApiError } from '../../api/client'
import { MemoEditorView } from './MemoEditor'
import {
  canWriteMemo,
  isMemoWriter,
  errorKeyFor,
  initialLang,
  isStateChanged,
  ORIGINAL_MAX,
  originalLength,
  originalProblem,
  type Memo,
} from './memoEditorLogic'

// 様子のメモを書く画面のテスト（spec 007 の 007-T011。FR-001・FR-003・FR-016・FR-017・FR-020）

const ORIGINAL = 'Hari ini Ibu kurang tersenyum dibanding biasanya, tapi makan siangnya habis.'
const REWRITTEN = '今日はいつもより笑顔が少なめでしたが、お昼ごはんは全部召し上がりました。'

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
          display_name: 'さくら 花子',
          display_name_ruby: 'さくら 花子',
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

describe('MemoEditorView（書く前）', () => {
  it('画面の上に、いつも「急変・事故は、すぐに電話で連絡してください」が出る（FR-016）', () => {
    expect(visibleText(render())).toContain('急変・事故は、すぐに電話で連絡してください')
    // 書いたあとも、AI が止まったときも、出たまま
    expect(visibleText(render({ memo: memo({ rewritten_text: REWRITTEN }) }))).toContain(
      '急変・事故は、すぐに電話で連絡してください',
    )
    expect(visibleText(render({ memo: memo(), errorKey: 'memo.unavailable' }))).toContain(
      '急変・事故は、すぐに電話で連絡してください',
    )
  })

  it('入居者の呼び名・居室、原文の言語（日本語・インドネシア語・英語）、書く欄と文字数が出る', () => {
    const html = render({ text: 'Hari ini' })
    const text = visibleText(html)

    expect(text).toContain('203')
    expect(text).toContain('さくら 花子')
    for (const name of ['日本語', 'Bahasa Indonesia', 'English']) expect(text).toContain(name)
    expect(html).toContain('<textarea')
    expect(text).toContain('8 / 500')
    // 選んだ言語が選ばれている
    expect(html).toMatch(/<option value="id" selected=""/)
  })

  it('何も書いていないときは「日本語にする」を押せない', () => {
    expect(render({ text: '' })).toMatch(/<button type="submit" disabled=""/)
    expect(render({ text: '  \n ' })).toMatch(/<button type="submit" disabled=""/)
    expect(render({ text: ORIGINAL })).not.toMatch(/<button type="submit" disabled=""/)
  })

  it('原文が日本語のときは、ボタンの名前が「整える」になる（FR-003）', () => {
    const ja = memo({ source_lang: 'ja', rewritten_text: REWRITTEN })

    expect(visibleText(render({ lang: 'ja', text: 'あ' }))).toContain('整える')
    expect(visibleText(render({ lang: 'ja', text: 'あ', pending: true }))).toContain(
      '整えています…',
    )
    expect(visibleText(render({ lang: 'ja', memo: ja }))).toContain('整え直す')
    // 日本語以外のときは、今までどおり
    expect(visibleText(render({ lang: 'en', text: 'Hello' }))).toContain('日本語にする')
    expect(visibleText(render({ lang: 'ja', text: 'あ' }))).not.toContain('日本語にする')
  })

  it('500 文字を超えると、案内を出して、押せない（FR-001）', () => {
    const html = render({ text: 'あ'.repeat(501) })

    expect(visibleText(html)).toContain('500 文字までで書いてください')
    expect(html).toMatch(/<button type="submit" disabled=""/)
    expect(render({ text: 'あ'.repeat(500) })).not.toMatch(/<button type="submit" disabled=""/)
  })

  it('整えている間は、押せず「日本語にしています…」と出る', () => {
    const html = render({ text: ORIGINAL, pending: true })

    expect(visibleText(html)).toContain('日本語にしています…')
    expect(html).toMatch(/<button type="submit" disabled=""/)
  })

  it('書いている文は、そのまま文字として出る（タグは実行されない。FR-017）', () => {
    const html = render({ text: '<img src=x onerror=alert(1)>' })

    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;')
  })
})

describe('MemoEditorView（整えたあと）', () => {
  it('原文と整えた日本語が、どちらも出る（シナリオ 1）。AI であることと、下書きであることも出る', () => {
    const text = visibleText(render({ memo: memo({ rewritten_text: REWRITTEN }) }))

    expect(text).toContain(ORIGINAL)
    expect(text).toContain(REWRITTEN)
    expect(text).toContain('職員が書いた内容を、AI で読みやすい日本語に整えています')
    expect(text).toContain('下書きとして保存しました。家族には、まだ見えません')
    expect(text).toContain('もう一度日本語にする')
  })

  it('下書きは、原文も整えた日本語も直せる（書く欄が 2 つ。FR-008）。言語は変えられない', () => {
    const html = render({ memo: memo({ rewritten_text: REWRITTEN }) })

    expect(html.match(/<textarea/g)).toHaveLength(2)
    expect(visibleText(html)).toContain('書いた原文は保存しました')
    expect(html).toMatch(/<select[^>]*disabled=""/)
  })

  it('承認待ち・承認済み・取り下げたメモは、読むだけ（書く欄も、日本語にするボタンも出ない）', () => {
    for (const status of ['pending', 'approved', 'withdrawn'] as const) {
      const html = render({ memo: memo({ status, rewritten_text: REWRITTEN }) })

      expect(html).not.toContain('<textarea')
      expect(html).not.toMatch(/<button type="submit"/)
      expect(visibleText(html)).toContain(ORIGINAL)
      expect(visibleText(html)).toContain(REWRITTEN)
    }
  })

  it('原文・整えた日本語は、文字のまま出る（HTML・ふりがなとして読まない。FR-017）', () => {
    const html = render({
      memo: memo({
        original_text: '<script>alert(1)</script> {漢字|かんじ}',
        rewritten_text: '<b>整えた</b>',
      }),
    })

    expect(html).not.toContain('<script>')
    expect(html).not.toContain('<b>')
    expect(visibleText(html)).toContain('<script>alert(1)</script> {漢字|かんじ}')
    expect(visibleText(html)).toContain('<b>整えた</b>')
  })
})

describe('MemoEditorView（AI が止まったとき。シナリオ 5）', () => {
  it('「いま日本語にできません」を出し、書いた原文は消えず、もう一度押せる（FR-020）', () => {
    const html = render({ memo: memo(), errorKey: 'memo.unavailable' })
    const text = visibleText(html)

    expect(text).toContain('いま日本語にできません。時間をおいてもう一度お試しください')
    expect(text).toContain(ORIGINAL)
    expect(text).toContain('もう一度押す')
    // 整えた日本語は、まだない
    expect(text).not.toContain('下書きとして保存しました')
    expect(html).not.toMatch(/<button type="submit" disabled=""/)
  })

  it('下書きを保存する前に失敗したとき（原文はまだ書く欄にある）も、文言が出る', () => {
    const html = render({ text: ORIGINAL, errorKey: 'error.server_error' })

    expect(html).toContain('<textarea')
    expect(html).toContain('role="alert"')
  })
})

describe('様子のメモを書ける役割（PR #249 ゆう）', () => {
  it('介護職員・リーダーだけが書ける。ほかの役割と、職員でない人には、最初に案内を出す', () => {
    expect(canWriteMemo('care_worker')).toBe(true)
    expect(canWriteMemo('leader')).toBe(true)
    for (const role of ['counselor', 'clerk', 'director'] as const) {
      expect(canWriteMemo(role)).toBe(false)
    }
    // 家族など、職員の役割がない人
    expect(canWriteMemo(null)).toBe(false)
  })

  it('役割がまだ分からない（読み込み中）ときは、案内を出さない', () => {
    expect(canWriteMemo(undefined)).toBe(true)
  })

  it('役割の判定は 1 つ：記録の画面のボタンは、読み込み中は出さない（#94）', () => {
    expect(isMemoWriter('care_worker')).toBe(true)
    expect(isMemoWriter('leader')).toBe(true)
    for (const role of ['counselor', 'clerk', 'director', null, undefined] as const) {
      expect(isMemoWriter(role)).toBe(false)
    }
  })

  it('案内の文言が、ふりがなを外して読める', () => {
    expect(i18n.t('memo.not_allowed').replace(/\{([^|}]+)\|[^}]+\}/g, '$1')).toBe(
      'この役割では、様子のメモは書けません',
    )
  })
})

describe('memoEditorLogic.ts', () => {
  it('原文の言語の初期値は、職員の表示言語（扱えない言語・未取得は日本語。R-12）', () => {
    expect(initialLang('id')).toBe('id')
    expect(initialLang('en')).toBe('en')
    expect(initialLang('ja')).toBe('ja')
    expect(initialLang('fr')).toBe('ja')
    expect(initialLang(undefined)).toBe('ja')
  })

  it('文字数は、前後の空白を数えず、絵文字なども 1 文字（backend と同じ）', () => {
    expect(originalLength('  あい  ')).toBe(2)
    expect(originalLength('😀😀')).toBe(2)
    expect(originalProblem('')).toBe('empty')
    expect(originalProblem(' \n ')).toBe('empty')
    expect(originalProblem('あ'.repeat(ORIGINAL_MAX))).toBeNull()
    expect(originalProblem('あ'.repeat(ORIGINAL_MAX + 1))).toBe('too_long')
  })

  it('AI が止まったとき（503 ai_unavailable）は、書く画面の文言。ほかは共通のエラーの文言', () => {
    expect(errorKeyFor(new ApiError(503, 'ai_unavailable', 'error.ai_unavailable'))).toBe(
      'memo.unavailable',
    )
    expect(errorKeyFor(new ApiError(404, 'not_found', 'error.not_found'))).toBe('error.not_found')
    expect(errorKeyFor(new Error('x'))).toBe('error.server_error')
  })

  it('状態が変わっていた（409 invalid_state）ときだけ、画面を読み直す（isStateChanged。#96）', () => {
    expect(isStateChanged(new ApiError(409, 'invalid_state', 'error.invalid_state'))).toBe(true)
    // 同じ 409 でも、状態の食い違いではないもの（回数の上限など）は、読み直さない
    expect(isStateChanged(new ApiError(409, 'memo_limit', 'error.memo_limit'))).toBe(false)
    expect(isStateChanged(new ApiError(503, 'ai_unavailable', 'error.ai_unavailable'))).toBe(false)
    expect(isStateChanged(new Error('x'))).toBe(false)
    expect(isStateChanged(null)).toBe(false)
    // 文言は共通のまま（MemoEditorConfirm.test.tsx で確かめている）
    expect(errorKeyFor(new ApiError(409, 'invalid_state', 'error.invalid_state'))).toBe(
      'error.invalid_state',
    )
  })

  it('文言が、ふりがなを外して読める', () => {
    expect(i18n.t('memo.language').replace(/\{([^|}]+)\|[^}]+\}/g, '$1')).toBe('原文の言語')
  })
})
