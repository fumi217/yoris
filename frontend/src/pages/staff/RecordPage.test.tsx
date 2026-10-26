import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { RecordView } from './RecordPage'
import {
  currentValue,
  firstUnrecordedMealSlot,
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
  resident: { id: 3, display_name: '佐藤さんの母', room: '101' },
  records,
  replies: [],
})

const render = (props: Partial<Parameters<typeof RecordView>[0]> = {}) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <RecordView
        book={book()}
        waitingRequests={0}
        saving={null}
        saved={false}
        errorKey={null}
        onChoose={() => {}}
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
    expect(render({ errorKey: 'error.not_today' })).toContain('直せます')
  })

  it('保存中は、続けて押せない', () => {
    const html = render({ saving: { item: 'meal', slot: 'breakfast', value: '8' } })

    expect(html.match(/disabled=""/g)).toHaveLength(12)
  })

  it('入居者の呼び名は、HTML として解釈しない', () => {
    const html = render({
      book: { ...book(), resident: { id: 3, display_name: '<i>x</i>', room: '101' } },
    })

    expect(html).not.toContain('<i>x</i>')
  })
})
