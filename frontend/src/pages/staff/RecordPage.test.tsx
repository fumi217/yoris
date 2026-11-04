import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { RecordView } from './RecordPage'
import {
  currentValue,
  firstUnrecordedMealSlot,
  withoutRecord,
  withRecord,
  type StaffContactBook,
  type StaffRecord,
} from './recordValues'

const record = (overrides: Partial<StaffRecord>): StaffRecord => ({
  id: 1,
  item: 'meal',
  slot: 'breakfast',
  value: '8',
  recorded_at: '2026-10-26T08:00:00+09:00',
  recorded_by_name: '職員A',
  ...overrides,
})

const book = (records: StaffRecord[] = []): StaffContactBook => ({
  date: '2026-10-26',
  resident: { id: 3, display_name: '佐藤 文江', display_name_ruby: '佐藤 文江', room: '101' },
  records,
  replies: [],
})

const render = (props: Partial<Parameters<typeof RecordView>[0]> = {}) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <RecordView
        book={book()}
        waitingRequests={0}
        canWriteMemo={false}
        saving={null}
        cancelling={false}
        notice={null}
        errorKey={null}
        onChoose={() => {}}
        onCancel={() => {}}
        {...props}
      />
    </MemoryRouter>,
  )

describe('recordValues', () => {
  it('今付いている値を、項目と区分で探す', () => {
    const records = [record({}), record({ id: 2, item: 'mood', slot: 'day', value: 'smile' })]

    expect(currentValue(records, 'meal', 'breakfast')).toBe('8')
    expect(currentValue(records, 'mood', 'day')).toBe('smile')
    expect(currentValue(records, 'meal', 'lunch')).toBeNull()
  })

  it('食事は、まだ記録していない最初の区分を開いておく', () => {
    expect(firstUnrecordedMealSlot([])).toBe('breakfast')
    expect(firstUnrecordedMealSlot([record({})])).toBe('lunch')
  })

  it('押し直したら、同じ項目・区分の記録を置き換える', () => {
    const updated = withRecord(book([record({})]), record({ id: 1, value: '5' }))

    expect(updated.records).toHaveLength(1)
    expect(updated.records[0].value).toBe('5')
  })

  it('取り消したら、その記録を外す', () => {
    expect(withoutRecord(book([record({})]), 1).records).toEqual([])
  })
})

describe('RecordView', () => {
  it('食事の 5 段階と「食事なし」、機嫌・眠りの 3 段階のボタンがある', () => {
    const html = render()

    // 食事 6 ＋ 機嫌 3 ＋ 眠り 3
    expect(html.match(/aria-pressed=/g)).toHaveLength(12)
    expect(html).toContain('外泊')
  })

  it('今付いている値のボタンは、押された状態になる', () => {
    const html = render({ book: book([record({ item: 'mood', slot: 'day', value: 'low' })]) })

    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1)
  })

  it('返事待ちがあれば、返事の画面へのリンクを出す', () => {
    expect(render()).not.toContain('/staff/residents/3/requests')
    expect(render({ waitingRequests: 2 })).toContain('href="/staff/residents/3/requests"')
  })

  it('保存できなかったら、理由を出す', () => {
    expect(render({ errorKey: 'error.not_today' })).toContain('したりできます')
  })

  it('保存中は、続けて押せない', () => {
    const html = render({ saving: { item: 'meal', slot: 'breakfast', value: '8' } })

    // ボタンが増えても数え直さなくて済むよう、「値のボタンがすべて押せない」で確かめる（PR #216 みさき）。
    // 食事の区分のタブは、保存中も切り替えられる
    const choices = (html.match(/<button[^>]*>/g) ?? []).filter((b) => b.includes('aria-pressed'))
    expect(choices.length).toBeGreaterThan(0)
    expect(choices.every((button) => button.includes('disabled=""'))).toBe(true)
  })

  it('入居者の呼び名は、HTML として解釈しない', () => {
    const html = render({
      book: {
        ...book(),
        resident: { id: 3, display_name: '<i>x</i>', display_name_ruby: '<i>x</i>', room: '101' },
      },
    })

    expect(html).not.toContain('<i>x</i>')
  })

  it('記録がある欄だけに「この記録を取り消す」を出す', () => {
    expect(render()).not.toContain('この<ruby>記録')
    const html = render({ book: book([record({ item: 'mood', slot: 'day', value: 'low' })]) })

    // 機嫌の欄だけ（食事の朝ごはん・眠りは記録がない）
    expect(html.match(/この<ruby>記録/g)).toHaveLength(1)
  })

  it('取り消したら、そう知らせる', () => {
    expect(render({ notice: 'cancelled' })).toContain('しました')
    expect(render({ notice: 'cancelled' })).toContain('取<rp>')
  })

  it('取り消し中は、ほかのボタンも押せない', () => {
    const html = render({ cancelling: true })

    // ボタンが増えても数え直さなくて済むよう、「値のボタンがすべて押せない」で確かめる（PR #216 みさき）。
    // 食事の区分のタブは、保存中も切り替えられる
    const choices = (html.match(/<button[^>]*>/g) ?? []).filter((b) => b.includes('aria-pressed'))
    expect(choices.length).toBeGreaterThan(0)
    expect(choices.every((button) => button.includes('disabled=""'))).toBe(true)
  })

  it('「写真を載せる」から、その入居者の写真の画面へ進む', () => {
    expect(render()).toContain('href="/staff/residents/3/album"')
  })

  it('「様子のメモを書く」から、その入居者のメモを書く画面へ進む', () => {
    expect(render({ canWriteMemo: true })).toContain('href="/staff/residents/3/memos/new"')
  })

  it('メモを書けない役割には、「様子のメモを書く」を出さない', () => {
    expect(render({ canWriteMemo: false })).not.toContain('/memos/new')
  })
})

describe('RecordView の変化の目印の欄（spec 006 の 006-T015）', () => {
  it('目印の欄を、記録のボタン・写真・様子のメモより上に置く', () => {
    const html = render({
      flagPanel: <section data-testid="flag-panel">目印の欄</section>,
      canWriteMemo: true,
    })

    const panel = html.indexOf('目印の欄')
    expect(panel).toBeGreaterThan(-1)
    expect(panel).toBeLessThan(html.indexOf('/album'))
    expect(panel).toBeLessThan(html.indexOf('/memos/new'))
    expect(panel).toBeLessThan(html.indexOf('role="tablist"'))
  })

  it('目印の欄を渡さなければ、何も出さない', () => {
    expect(render()).not.toContain('目印の欄')
  })
})

describe('記録の画面の見た目（#439）', () => {
  const text = (html: string) =>
    html
      .replace(/<rt>.*?<\/rt>/g, '')
      .replace(/<rp>.*?<\/rp>/g, '')
      .replace(/<[^>]+>/g, '')

  it('「今日の記録」の札に、記録済みは値、まだは「未記録」を出す（おやつは数えない）', () => {
    const html = render({
      book: book([
        record({ slot: 'breakfast', value: '10' }),
        record({ id: 2, item: 'mood', slot: 'day', value: 'smile' }),
      ]),
    })
    const shown = text(html)

    expect(shown).toContain('今日の記録')
    expect(shown).toMatch(/朝.*全部/)
    expect(shown).toMatch(/機嫌.*笑顔が多い/)
    // 札は 5 つ（朝・昼・夜・機嫌・眠り）。まだは 3 つ
    expect(html.match(/border-dashed border-field-line bg-card text-ink-sub/g)).toHaveLength(3)
  })

  it('「食事なし」は、札では短い名前にする', () => {
    const shown = text(render({ book: book([record({ slot: 'breakfast', value: 'none' })]) }))

    expect(shown).toContain('食事なし')
  })

  it('食べた量のボタンには、お皿の絵（飾り）を付ける。「食事なし」は点線の別のボタン', () => {
    const html = render()

    // お皿の絵は 5 つ（全部・ほぼ全部・半分・少し・食べていない）
    expect(html.match(/<svg width="34"/g)).toHaveLength(5)
    expect(html).toMatch(/<button[^>]*aria-pressed="false"[^>]*class="[^"]*border-dashed/)
  })

  it('機嫌・眠りのボタンには、顔の絵を付ける', () => {
    const html = render()

    expect(html).toContain('data-icon="face-smile"')
    expect(html).toContain('data-icon="face-meh"')
    expect(html).toContain('data-icon="face-frown"')
  })

  it('選ばれたボタンには、色に加えて ✔ を出す', () => {
    const html = render({ book: book([record({ item: 'mood', slot: 'day', value: 'low' })]) })

    const pressed = html.match(/<button[^>]*aria-pressed="true"[\s\S]*?<\/button>/)?.[0] ?? ''
    expect(pressed).toContain('data-icon="check"')
  })

  it('記録があれば、記録した人と時刻を出す（名前はふりがなの書き方として解釈しない）', () => {
    const html = render({
      book: book([
        record({ item: 'mood', slot: 'day', value: 'low', recorded_by_name: '職員{A|え}' }),
      ]),
    })

    expect(text(html)).toContain('08:00')
    expect(html).not.toContain('<rt>え</rt>')
  })

  it('保存の知らせは、その欄の見出しの横に出す', () => {
    const html = render({ notice: 'saved', noticeAt: 'sleep' })
    const sleep = html.slice(html.indexOf('id="record-sleep"'))

    expect(text(sleep)).toContain('保存しました')
    expect(text(html.slice(0, html.indexOf('id="record-sleep"')))).not.toContain('保存しました')
  })

  it('食事の問いは、区分の名前を差し込んだ 1 つの文にする（言語ごとに語順が違うため）', () => {
    const shown = text(render({ book: book([record({ slot: 'breakfast', value: '10' })]) }))

    expect(shown).toContain('昼ごはんは、どのくらい食べましたか')
  })
})
