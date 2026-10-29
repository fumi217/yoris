import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import i18n from '../../i18n'
import { ChangeFlagPanelView } from './ChangeFlagPanel'
import type { ChangeFlag, ChangeFlags } from './changeFlags'
import { confirmBody, noteLength } from './changeFlags'

// ふりがな（<ruby>・<rt>・<rp>）を外して、画面に出る文字だけで比べる
function text(html: string): string {
  return html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')
}

function render(data: ChangeFlags, props: { conflict?: boolean; errorKey?: string | null } = {}) {
  return renderToStaticMarkup(
    <ChangeFlagPanelView
      data={data}
      saving={false}
      conflict={props.conflict ?? false}
      errorKey={props.errorKey ?? null}
      onConfirm={() => {}}
    />,
  )
}

const mealFlag = (changes: Partial<ChangeFlag> = {}): ChangeFlag => ({
  id: 12,
  rule_code: 'meal_low',
  started_at: '2026-10-21T00:10:00Z',
  streak: 2,
  status: 'unconfirmed',
  evidence: [
    { record_id: 301, date: '2026-10-20', slot: 'dinner', value: '2' },
    { record_id: 305, date: '2026-10-21', slot: 'breakfast', value: '0' },
  ],
  confirmations: [],
  ...changes,
})

const moodFlag = (changes: Partial<ChangeFlag> = {}): ChangeFlag => ({
  id: 13,
  rule_code: 'mood_low',
  started_at: '2026-10-21T00:10:00Z',
  streak: 2,
  status: 'unconfirmed',
  evidence: [
    { record_id: 310, date: '2026-10-20', slot: 'day', value: 'low' },
    { record_id: 311, date: '2026-10-21', slot: 'day', value: 'low' },
  ],
  confirmations: [],
  ...changes,
})

describe('目印の欄（spec 006 の T006・T013）', () => {
  it('当てはまった決まりを、もとの記録から辞書で組み立てて出す（食事）', () => {
    const shown = text(render({ current: [mealFlag()], history: [] }))

    expect(shown).toContain('⚠️ いつもと違う様子')
    expect(shown).toContain('食事量：10月20日の夜ごはんから 2 食続けて、少し以下')
    // もとになった記録（日付・項目・区分・値）
    expect(shown).toContain('10月20日 食事（夜）：少し')
    expect(shown).toContain('10月21日 食事（朝）：食べていない')
  })

  it('機嫌・眠りは、区分を付けずに出す（1 日に 1 つ）', () => {
    const shown = text(
      render({
        current: [
          moodFlag(),
          moodFlag({
            id: 14,
            rule_code: 'sleep_poor',
            evidence: [
              { record_id: 320, date: '2026-10-20', slot: 'day', value: 'poor' },
              { record_id: 321, date: '2026-10-21', slot: 'day', value: 'poor' },
            ],
          }),
        ],
        history: [],
      }),
    )

    expect(shown).toContain('機嫌：10月20日から 2 日続けて、元気がない')
    expect(shown).toContain('10月20日 機嫌：元気がない')
    expect(shown).toContain('眠り：10月20日から 2 日続けて、あまり眠れなかった')
    expect(shown).toContain('10月21日 眠り：あまり眠れなかった')
  })

  it('もとの記録は、API の順によらず日付の古い順に並べる', () => {
    const flag = mealFlag()
    const reversed = mealFlag({ evidence: [...flag.evidence].reverse() })

    expect(text(render({ current: [reversed], history: [] }))).toContain(
      '食事量：10月20日の夜ごはんから',
    )
  })

  it('そばに、看護職員・生活相談員への案内を出す（FR-004）', () => {
    const shown = text(render({ current: [mealFlag()], history: [] }))

    expect(shown).toContain('気になるときは、看護職員・生活相談員に相談してください。急変は電話で')
  })

  it('まだ確かめていない目印には、「確かめた」とひとこと欄（100 文字まで・任意）を出す', () => {
    const html = render({ current: [mealFlag()], history: [] })
    const shown = text(html)

    expect(shown).toContain('まだ確かめていません')
    expect(shown).toContain('確かめた')
    expect(shown).toContain('ひとこと（任意。100 文字まで）')
    expect(shown).toContain('0 / 100')
    expect(html).toContain('<textarea')
    expect(html).toContain('aria-describedby="change-note-count"')
    expect(html).toContain('type="submit"')
  })

  it('確かめ済みの目印は区別し、確かめた人・日・ひとことを出す。確かめる欄は出さない', () => {
    const html = render({
      current: [
        mealFlag({
          status: 'confirmed',
          confirmations: [
            {
              staff_display_name: '田中',
              confirmed_at: '2026-10-21T03:00:00Z',
              note: '本人は元気。様子見',
            },
          ],
        }),
      ],
      history: [],
    })
    const shown = text(html)

    expect(shown).toContain('✔ 確かめ済み')
    expect(shown).toContain('確かめた人：田中（10月21日）')
    expect(shown).toContain('ひとこと：本人は元気。様子見')
    expect(shown).not.toContain('まだ確かめていません')
    expect(html).not.toContain('<textarea')
    expect(html).not.toContain('type="submit"')
  })

  it('確かめたあとに続いて戻った目印は、前に確かめた記録を残したまま、また確かめられる', () => {
    const html = render({
      current: [
        mealFlag({
          status: 'unconfirmed',
          confirmations: [
            { staff_display_name: '田中', confirmed_at: '2026-10-21T03:00:00Z', note: null },
          ],
        }),
      ],
      history: [],
    })
    const shown = text(html)

    expect(shown).toContain('まだ確かめていません')
    expect(shown).toContain('確かめた人：田中')
    expect(html).toContain('<textarea')
  })

  it('ひとこと・職員の名前は文字のまま出す（タグも、ふりがなの書き方も解釈しない。FR-013）', () => {
    const html = render({
      current: [
        mealFlag({
          status: 'confirmed',
          confirmations: [
            {
              staff_display_name: '田中{太郎|たろう}',
              confirmed_at: '2026-10-21T03:00:00Z',
              note: '<script>alert(1)</script>',
            },
          ],
        }),
      ],
      history: [],
    })

    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(text(html)).toContain('確かめた人：田中{太郎|たろう}')
  })

  it('過去の目印を新しい順に並べ、付いた日・消えた日・確かめた人を出す（FR-008）', () => {
    const shown = text(
      render({
        current: [],
        history: [
          moodFlag({
            id: 7,
            status: 'cleared',
            started_at: '2026-10-21T00:10:00Z',
            cleared_at: '2026-10-23T01:00:00Z',
            cleared_reason: 'not_matching',
            confirmations: [
              {
                staff_display_name: '田中',
                confirmed_at: '2026-10-22T03:00:00Z',
                note: '様子見',
              },
            ],
          }),
        ],
      }),
    )

    expect(shown).toContain('過去の目印')
    expect(shown).toContain('機嫌：10月20日から 2 日続けて、元気がない')
    expect(shown).toContain('付いた日：10月21日')
    expect(shown).toContain('消えた日：10月23日')
    expect(shown).toContain('確かめた人：田中（10月22日）')
    // 今の目印がないので、「確かめた」の欄と案内は出さない
    expect(shown).not.toContain('急変は電話で')
    expect(shown).not.toContain('⚠️ いつもと違う様子')
  })

  it('今も過去も目印がなければ、欄ごと出さない', () => {
    expect(render({ current: [], history: [] })).toBe('')
  })

  it('知らない決まりのコードは、文を作れないので出さない（画面が壊れない）', () => {
    const shown = text(render({ current: [mealFlag({ rule_code: 'unknown_rule' })], history: [] }))

    expect(shown).not.toContain('unknown_rule')
  })

  it('ほかの職員が先に確かめたときは、その案内を出す（409。FR-009）', () => {
    const shown = text(render({ current: [mealFlag()], history: [] }, { conflict: true }))

    expect(shown).toContain('ほかの職員が確かめました')
  })

  it('確かめられなかったときは、理由を出す', () => {
    const html = render({ current: [mealFlag()], history: [] }, { errorKey: 'error.server_error' })

    expect(html).toContain('role="alert"')
    expect(text(html)).toContain('うまくいきませんでした')
  })
})

describe('確かめる API に送る内容（T018）', () => {
  it('ひとことは前後の空白を取り、空なら送らない', () => {
    expect(confirmBody('  様子見  ')).toEqual({ note: '様子見' })
    expect(confirmBody('')).toEqual({})
    expect(confirmBody('  \n ')).toEqual({})
  })

  it('文字数は、絵文字なども 1 文字と数える（backend の数え方と同じ）', () => {
    expect(noteLength('あ'.repeat(100))).toBe(100)
    expect(noteLength('😀'.repeat(100))).toBe(100)
  })
})

describe('辞書の目印まわり（change.*。SC-003・research.md R-06）', () => {
  const leaves = (value: unknown): string[] =>
    typeof value === 'string'
      ? [value]
      : Object.values((value ?? {}) as Record<string, unknown>).flatMap(leaves)
  const sentences = leaves(i18n.getResource('ja', 'translation', 'change'))

  it('日本語の文が辞書にある', () => {
    expect(sentences.length).toBeGreaterThan(10)
  })

  it('医療の言葉（病気・疑い・診断・症状・脱水 など）が入っていない', () => {
    const medical = [
      '病',
      '疑い',
      '診断',
      '症状',
      '脱水',
      '治療',
      '服薬',
      '薬',
      '感染',
      '認知症',
      '熱',
    ]
    for (const sentence of sentences) {
      for (const word of medical) {
        expect(sentence, `「${word}」が入っている：${sentence}`).not.toContain(word)
      }
    }
  })

  it('ふりがなのない漢字がない（職員の画面なので、すべての漢字にふりがなを付ける）', () => {
    for (const sentence of sentences) {
      const bare = sentence.replace(/\{[^{}|]+\|[^{}|]+\}/g, '').replace(/\{\{[^}]+\}\}/g, '')
      expect(bare, `ふりがなのない漢字がある：${sentence}`).not.toMatch(/[㐀-鿿]/)
    }
  })
})
