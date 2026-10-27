import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { recordLabelKey, shiftDate, timeInJapan, timeline } from './contactBookTimeline'
import type { StaffContactBook, StaffRecord, StaffReply } from './recordValues'
import { ContactBookView } from './StaffContactBook'

const record = (overrides: Partial<StaffRecord> = {}): StaffRecord => ({
  id: 1,
  item: 'meal',
  slot: 'lunch',
  value: '8',
  recorded_at: '2026-10-26T12:30:00+09:00',
  recorded_by_name: '職員A',
  ...overrides,
})

const reply = (overrides: Partial<StaffReply> = {}): StaffReply => ({
  id: 9,
  request_id: 5,
  theme_code: 'theme.meals',
  theme_emoji: '🍚',
  template_codes: ['template.meals.well'],
  note: null,
  replied_by_name: '職員B',
  replied_at: '2026-10-26T10:00:00+09:00',
  edited: false,
  read: false,
  template_ids: [21],
  template_options: [
    { id: 21, code: 'template.meals.well' },
    { id: 22, code: 'template.meals.less' },
  ],
  editable: true,
  ...overrides,
})

const book = (records: StaffRecord[] = [], replies: StaffReply[] = []): StaffContactBook => ({
  date: '2026-10-26',
  resident: { id: 3, display_name: '佐藤さんの母', room: '101' },
  records,
  replies,
})

const render = (value: StaffContactBook, editable = false) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ContactBookView book={value} onEditReply={editable ? () => {} : undefined} />
    </MemoryRouter>,
  )

describe('contactBookTimeline', () => {
  it('記録と返事を、時刻の古い順に 1 本にする', () => {
    const entries = timeline(book([record()], [reply()]))

    expect(entries.map((entry) => entry.kind)).toEqual(['reply', 'record'])
  })

  it('時刻は日本時間で出す', () => {
    expect(timeInJapan('2026-10-26T03:05:00Z')).toBe('12:05')
  })

  it('食事は区分の名前、機嫌・眠りは項目の名前で出す', () => {
    expect(recordLabelKey(record())).toBe('record_page.slot.lunch')
    expect(recordLabelKey(record({ item: 'sleep', slot: 'day' }))).toBe('record.item.sleep')
  })

  it('前の日・次の日は、月・年をまたいでもずれない', () => {
    expect(shiftDate('2026-11-01', -1)).toBe('2026-10-31')
    expect(shiftDate('2026-12-31', 1)).toBe('2027-01-01')
  })
})

describe('ContactBookView', () => {
  it('記録と返事を、記録した人・返事をした人とともに出す', () => {
    const html = render(book([record()], [reply()]))

    expect(html).toContain('12:30')
    expect(html).toContain('職員A')
    expect(html).toContain('職員B')
    expect(html.indexOf('職員B')).toBeLessThan(html.indexOf('職員A'))
  })

  it('職員が書き足した文は、HTML として解釈しない', () => {
    const html = render(book([], [reply({ note: '<script>alert(1)</script>' })]))

    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })

  it('前の日・次の日へのリンクがある', () => {
    const html = render(book())

    expect(html).toContain('href="/staff/residents/3/contact-book?date=2026-10-25"')
    expect(html).toContain('href="/staff/residents/3/contact-book?date=2026-10-27"')
  })

  it('その日に何もなければ、そう伝える', () => {
    expect(render(book())).toContain('ありません')
  })

  it('今日の返事だけに「この返事を直す」を出す', () => {
    expect(render(book([], [reply()]), true)).toContain('<ruby>直')
    expect(render(book([], [reply({ editable: false })]), true)).not.toContain('<ruby>直</ruby>')
    // 直す関数を渡さないとき（読むだけのとき）は出さない
    expect(render(book([], [reply()]))).not.toContain('この<ruby>返事')
  })
})
