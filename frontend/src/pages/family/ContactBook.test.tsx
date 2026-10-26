import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import '../../i18n'
import { ContactBookView } from './ContactBook'
import {
  markSentOnce,
  monthDayOf,
  slotLabelKey,
  timeInJapan,
  valueKey,
  type ContactBookData,
  type ContactReply,
  type ContactSection,
} from './contactBookView'

const reply = (overrides: Partial<ContactReply> = {}): ContactReply => ({
  id: 1,
  contact_book_date: '2026-10-26',
  theme_code: 'theme.daily_life',
  theme_emoji: '👀',
  template_codes: ['template.daily_life.usual'],
  note: null,
  replied_by_name: '西村（看護師）',
  replied_at: '2026-10-26T00:30:00Z',
  edited: false,
  read: false,
  ...overrides,
})

const NOT_RECORDED = 'contact_book.not_recorded'

const sections = (): ContactSection[] => [
  {
    item: 'meal',
    slots: [
      {
        slot: 'breakfast',
        record: {
          id: 1,
          value: '8',
          recorded_at: '2026-10-26T00:00:00Z',
          recorded_by_name: '田中',
        },
        message_key: null,
      },
      { slot: 'lunch', record: null, message_key: NOT_RECORDED },
    ],
  },
  { item: 'mood', slots: [{ slot: 'day', record: null, message_key: NOT_RECORDED }] },
]

const book = (overrides: Partial<ContactBookData> = {}): ContactBookData => ({
  date: '2026-10-26',
  unread_replies: [],
  day_replies: [],
  sections: sections(),
  ...overrides,
})

const render = (data: ContactBookData) =>
  renderToStaticMarkup(<ContactBookView book={data} onRead={vi.fn()} />)

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('ContactBookView', () => {
  it('未記録の欄に「まだ記録されていません」が出る（FR-017）', () => {
    const shown = text(render(book()))

    // 昼ごはんと機嫌・様子の 2 か所
    expect(shown.match(/まだ記録されていません/g)).toHaveLength(2)
  })

  it('記録した欄は、値と記録した職員・時刻が出る', () => {
    const shown = text(render(book()))

    expect(shown).toContain('ほぼ全部')
    expect(shown).toContain('田中 09:00')
  })

  it('未読の返事のカードが、記録より上に出る（FR-015）', () => {
    const shown = text(render(book({ unread_replies: [reply()] })))

    expect(shown).toContain('西村（看護師）からの返事')
    expect(shown.indexOf('西村（看護師）')).toBeLessThan(shown.indexOf('食事'))
  })

  it('別の日の未読の返事には、その日の連絡帳に入った返事だと添える', () => {
    const shown = text(
      render(book({ unread_replies: [reply({ contact_book_date: '2026-10-24' })] })),
    )

    expect(shown).toContain('10月24日の連絡帳に入った返事')
  })

  it('その日の返事には、日付を添えない', () => {
    const shown = text(render(book({ unread_replies: [reply()] })))

    expect(shown).not.toContain('に入った返事')
  })

  it('職員が書き足した文は、HTML として解釈しない', () => {
    const html = render(book({ unread_replies: [reply({ note: '<b>元気でした</b>' })] }))

    expect(html).not.toContain('<b>元気でした</b>')
    expect(html).toContain('&lt;b&gt;元気でした&lt;/b&gt;')
  })

  it('読んだ返事は、未読の印なしで出る', () => {
    const unread = text(render(book({ unread_replies: [reply()] })))
    const read = text(render(book({ day_replies: [reply({ read: true })] })))

    expect(unread).toContain('新しい返事')
    expect(read).toContain('西村（看護師）からの返事')
    expect(read).not.toContain('新しい返事')
  })

  it('返事がなければ、返事のカードは出ない', () => {
    expect(render(book())).not.toContain('<article')
  })

  it('画面の下に、緊急のときの案内が出る', () => {
    expect(text(render(book()))).toContain('緊急のときは、施設から電話します')
  })

  it('開示していない項目（API が返さなかったもの）は、出ない', () => {
    const shown = text(render(book({ sections: [sections()[0]] })))

    expect(shown).toContain('食事')
    expect(shown).not.toContain('機嫌')
  })
})

describe('contactBookView', () => {
  it('時刻は日本時間の HH:MM', () => {
    expect(timeInJapan('2026-10-26T00:30:00Z')).toBe('09:30')
  })

  it('日付を月と日に分ける', () => {
    expect(monthDayOf('2026-10-26')).toEqual({ month: 10, day: 26 })
  })

  it('食事だけ区分の名前を出す', () => {
    expect(slotLabelKey('meal', 'lunch')).toBe('record.slot.lunch')
    expect(slotLabelKey('mood', 'day')).toBeNull()
  })

  it('値の辞書のキーは項目ごと', () => {
    expect(valueKey('sleep', 'good')).toBe('record.value.sleep.good')
  })

  it('既読を送るのは、返事 1 つにつき 1 回だけ', () => {
    const sent = new Set<number>()

    expect(markSentOnce(sent, 5)).toBe(true)
    expect(markSentOnce(sent, 5)).toBe(false)
    expect(markSentOnce(sent, 6)).toBe(true)
  })
})
