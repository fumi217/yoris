import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import '../../i18n'
import { ContactBookView } from './ContactBook'
import {
  markSentOnce,
  monthDayOf,
  pickDate,
  sectionStatus,
  shiftDate,
  slotLabelKey,
  timeInJapan,
  todayInJapan,
  valueKey,
  weekdayOf,
  type ContactBookData,
  type ContactMemo,
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
  replied_by_name: '西村',
  replied_by_occupation: 'nurse',
  replied_at: '2026-10-26T00:30:00Z',
  edited: false,
  read: false,
  ...overrides,
})

const memo = (overrides: Partial<ContactMemo> = {}): ContactMemo => ({
  id: 1,
  text: '午後、お友だちと楽しそうに話していました。',
  author_name: 'シティ',
  author_occupation: 'care_worker',
  written_at: '2026-10-26T05:00:00Z',
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
  memos: [],
  sections: sections(),
  ...overrides,
})

const render = (data: ContactBookData) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ContactBookView book={data} onRead={vi.fn()} />
    </MemoryRouter>,
  )

const renderWithNav = (data: ContactBookData, today: string) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ContactBookView book={data} onRead={vi.fn()} today={today} onMove={vi.fn()} />
    </MemoryRouter>,
  )

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

  it('返事には、職員の名前と職種を出す（職種は辞書で引く。#263）', () => {
    const shown = text(
      render(
        book({
          unread_replies: [
            reply({ replied_by_name: 'シティ', replied_by_occupation: 'care_worker' }),
          ],
        }),
      ),
    )

    expect(shown).toContain('シティ（介護職員）からの返事')
  })

  it('職種が空なら、かっこを付けず名前だけを出す（役割では補わない。#263）', () => {
    const shown = text(
      render(
        book({ unread_replies: [reply({ replied_by_name: '高橋', replied_by_occupation: null })] }),
      ),
    )

    expect(shown).toContain('高橋からの返事')
    expect(shown).not.toContain('高橋（')
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

    expect(unread).toContain('new')
    expect(read).toContain('西村（看護師）からの返事')
    expect(read).not.toContain('new')
  })

  it('返事がなければ、返事のカードは出ない', () => {
    expect(render(book())).not.toContain('<article')
  })

  it('様子のメモは、職員の名前と書いた時刻、AI で整えている旨の注記つきで出る（FR-012）', () => {
    const shown = text(render(book({ memos: [memo()] })))

    expect(shown).toContain('様子のメモ')
    expect(shown).toContain('午後、お友だちと楽しそうに話していました。')
    expect(shown).toContain('シティ')
    expect(shown).toContain('14:00')
    expect(shown).toContain('職員が書いた内容を、AI で読みやすい日本語に整えています')
  })

  it('様子のメモは、書いた時刻の順（API が返した順）のまま並ぶ', () => {
    const shown = text(
      render(
        book({ memos: [memo({ id: 1, text: 'さきのメモ' }), memo({ id: 2, text: 'あとのメモ' })] }),
      ),
    )

    expect(shown.indexOf('さきのメモ')).toBeLessThan(shown.indexOf('あとのメモ'))
  })

  it('様子のメモがなければ、その欄も注記も出ない', () => {
    const shown = text(render(book()))

    expect(shown).not.toContain('様子のメモ')
    expect(shown).not.toContain('AI で読みやすい日本語')
  })

  it('様子のメモに書かれた HTML は、文字のまま出す', () => {
    const html = render(book({ memos: [memo({ text: '<script>alert(1)</script>' })] }))

    expect(html).not.toContain('<script>alert(1)</script>')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
  })

  it('画面の下に、緊急のときの案内が出る', () => {
    expect(text(render(book()))).toContain('緊急のときは、施設からお電話します')
  })

  it('開示していない項目（API が返さなかったもの）は、出ない', () => {
    const shown = text(render(book({ sections: [sections()[0]] })))

    expect(shown).toContain('食事')
    expect(shown).not.toContain('機嫌')
  })
})

describe('日付の切り替え（T094）', () => {
  it('過去の日を見ているときは、前の日・次の日・今日へのボタンと日付の選択が出る', () => {
    const html = renderWithNav(book({ date: '2026-10-26' }), '2026-10-27')
    const shown = text(html)

    // 前の日・次の日は、矢印のアイコンのボタン（名前は aria-label）
    expect(html).toContain('aria-label="前の日"')
    expect(html).toContain('aria-label="次の日"')
    expect(shown).toContain('今日の連絡帳に戻る')
    expect(html).toContain('type="date"')
    expect(html).toContain('max="2026-10-27"')
    expect(html).toContain('value="2026-10-26"')
  })

  it('今日を見ているときは、次の日が押せず、今日へのボタンは出ない', () => {
    const html = renderWithNav(book({ date: '2026-10-27' }), '2026-10-27')
    const past = renderWithNav(book({ date: '2026-10-26' }), '2026-10-27')

    // 押せないボタンは、今日を見ているときの「次の日」だけ
    expect(html).toContain('disabled=""')
    expect(past).not.toContain('disabled=""')
    expect(text(html)).not.toContain('今日の連絡帳に戻る')
  })

  it('今日を見ているときは、次の日が押せない理由を近くに書き、結びつける', () => {
    const html = renderWithNav(book({ date: '2026-10-27' }), '2026-10-27')
    const past = renderWithNav(book({ date: '2026-10-26' }), '2026-10-27')

    expect(text(html)).toContain('明日の記録は、まだありません')
    expect(html).toContain('aria-describedby="next-day-hint"')
    expect(text(past)).not.toContain('明日の記録は、まだありません')
  })

  it('日付の入力は、「もっと前の日を見る」の中に入れる（ふだんは閉じている）', () => {
    const html = renderWithNav(book({ date: '2026-10-27' }), '2026-10-27')

    expect(html).toMatch(/<details>.*もっと.*type="date"/s)
    expect(html).not.toContain('<details open')
  })

  it('食事は、狭い幅では 1 列・広い幅では 3 列。単語の途中で折り返さない', () => {
    const html = render(book())

    expect(html).toContain('grid-cols-1')
    expect(html).toContain('sm:grid-cols-3')
    expect(html).toContain('break-keep')
  })

  it('「今日の連絡帳に戻る」は、背景色のあるボタン', () => {
    const html = renderWithNav(book({ date: '2026-10-26' }), '2026-10-27')

    const button = html.match(/<button[^>]*>(?=<span><ruby>今日)/)?.[0] ?? ''

    expect(text(html)).toContain('今日の連絡帳に戻る')
    expect(button).toContain('bg-primary-soft')
  })

  it('「1 週間のまとめ」の入口（FR-036）：見出しの行にあり、/family/weekly へ移る', () => {
    const html = render(book())

    expect(html).toMatch(/<a[^>]*href="\/family\/weekly"/)
    expect(text(html)).toContain('1週間のまとめ')
    expect(html).toContain('data-icon="calendar-week"')
  })

  it('未読の返事は、生の sky ではなく unread の色と左の線で強調する', () => {
    const html = render(book({ unread_replies: [reply()] }))

    expect(html).toContain('bg-unread')
    expect(html).toContain('border-primary')
    expect(html).not.toContain('sky-')
  })

  it('日付の切り替えを渡さないときは、出ない（今までの画面のまま）', () => {
    expect(render(book())).not.toContain('type="date"')
  })

  it('過去の日でも、未読の返事は一番上に出る（日付に関わらない）', () => {
    const html = renderWithNav(
      book({ date: '2026-10-20', unread_replies: [reply({ contact_book_date: '2026-10-26' })] }),
      '2026-10-27',
    )

    expect(text(html)).toContain('new')
    expect(html.indexOf('<article')).toBeLessThan(html.indexOf('食事'))
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

  it('日付を日数ずらす（月・年をまたぐ。うるう日も）', () => {
    expect(shiftDate('2026-10-27', -1)).toBe('2026-10-26')
    expect(shiftDate('2026-11-01', -1)).toBe('2026-10-31')
    expect(shiftDate('2027-01-01', -1)).toBe('2026-12-31')
    expect(shiftDate('2028-03-01', -1)).toBe('2028-02-29')
    expect(shiftDate('2026-10-31', 1)).toBe('2026-11-01')
  })

  it('今日は日本時間で数える（日本の 0 時を過ぎたら、UTC ではまだ前の日でも次の日）', () => {
    expect(todayInJapan(new Date('2026-10-26T15:30:00Z'))).toBe('2026-10-27')
    expect(todayInJapan(new Date('2026-10-26T14:59:00Z'))).toBe('2026-10-26')
  })

  it('?date= は、正しい過去の日だけ使い、それ以外は今日にする', () => {
    const today = '2026-10-27'

    expect(pickDate('2026-10-20', today)).toBe('2026-10-20')
    expect(pickDate('2026-10-27', today)).toBe(today)
    expect(pickDate(null, today)).toBe(today)
    expect(pickDate('', today)).toBe(today)
    expect(pickDate('あした', today)).toBe(today)
    expect(pickDate('2026-13-40', today)).toBe(today)
    expect(pickDate('2026-02-30', today)).toBe(today)
    expect(pickDate('2026-10-28', today)).toBe(today)
    expect(pickDate('1999-01-01', today)).toBe('1999-01-01')
  })

  it('既読を送るのは、返事 1 つにつき 1 回だけ', () => {
    const sent = new Set<number>()

    expect(markSentOnce(sent, 5)).toBe(true)
    expect(markSentOnce(sent, 5)).toBe(false)
    expect(markSentOnce(sent, 6)).toBe(true)
  })
})

describe('連絡帳の見た目（#382）', () => {
  const recorded = (slot: string, value: string) => ({
    slot,
    record: { id: 9, value, recorded_at: '2026-10-26T00:00:00Z', recorded_by_name: '田中' },
    message_key: null,
  })
  const none = { slot: 'day', record: null, message_key: NOT_RECORDED }

  it('見出しに曜日を出し、今日は「本日のご様子をまとめています」、過去の日は「この日の…」', () => {
    const today = text(renderWithNav(book({ date: '2026-10-30' }), '2026-10-30'))
    const past = text(renderWithNav(book({ date: '2026-10-26' }), '2026-10-30'))

    expect(today).toContain('10月30日（金）の連絡帳')
    expect(today).toContain('本日のご様子をまとめています')
    expect(past).toContain('10月26日（月）の連絡帳')
    expect(past).toContain('当日のご様子をまとめています')
  })

  it('日付の操作は、前の日・今の日付・次の日を 1 つにつなげる（今日を見ているときは次の日が押せない）', () => {
    const html = renderWithNav(book({ date: '2026-10-30' }), '2026-10-30')
    const nav = html.slice(html.indexOf('aria-label="前の日"'), html.indexOf('type="date"'))

    expect(nav.indexOf('aria-label="前の日"')).toBeLessThan(nav.indexOf('10月30日（金）'))
    expect(nav.indexOf('10月30日（金）')).toBeLessThan(nav.indexOf('aria-label="次の日"'))
    expect(html).toMatch(/aria-label="次の日"[^>]*disabled=""|disabled=""[^>]*aria-label="次の日"/)
  })

  it('食事・機嫌・眠りは 1 枚のカードの中に入る（カードの中にカードを重ねない）', () => {
    const html = render(
      book({
        sections: [
          sections()[0],
          { item: 'mood', slots: [none] },
          { item: 'sleep', slots: [none] },
        ],
      }),
    )

    expect(html.match(/rounded-2xl border border-card-line/g)).toHaveLength(1)
    expect(html.match(/<h2/g)).toHaveLength(3)
  })

  it('食事は朝・昼・夜を横 3 列に並べ、区分ごとに小さなアイコン（飾り）が付く', () => {
    const html = render(book())

    expect(html).toContain('grid-cols-3')
    expect(html.match(/<svg[^>]*aria-hidden="true"/g)?.length).toBeGreaterThanOrEqual(3)
    expect(text(html)).toContain('食事の量や様子を記録しています')
  })

  it('機嫌・眠りが未記録のときは、中央に「まだ記録されていません」「施設からの記録をお待ちください」', () => {
    const shown = text(render(book()))

    expect(shown).toContain('施設からの記録をお待ちください')
    expect(shown).toContain('表情やご様子の変化を記録しています')
  })

  it('記録した機嫌は、値と記録した職員・時刻が出る（お待ちくださいは出ない）', () => {
    const shown = text(
      render(book({ sections: [{ item: 'mood', slots: [recorded('day', 'good')] }] })),
    )

    expect(shown).toContain('田中 09:00')
    expect(shown).not.toContain('施設からの記録をお待ちください')
  })

  it('各セクションの右に、状態の印（文字）を出す。色だけにしない', () => {
    const shown = text(render(book()))

    expect(shown).toContain('一部記録') // 食事：朝だけ記録済み
    expect(shown).toContain('未記録') // 機嫌
  })

  it('緊急の案内は、電話のアイコンつきの淡い青の帯（警告の赤・オレンジにしない）', () => {
    const html = render(book())
    const bar = html.slice(html.lastIndexOf('<p class="flex items-center gap-3'))

    expect(bar).toContain('bg-primary-soft')
    expect(bar).toContain('<svg')
    expect(bar).not.toMatch(/red|orange|amber/)
  })

  it('絵文字は出さない（返事のカードのテーマの絵文字だけは、データなので、④で置き換える）', () => {
    const html = render(book())

    expect(html).not.toMatch(/[\u{1F300}-\u{1FAFF}\u25C0\u25B6]/u)
  })
})

describe('contactBookView（#382）', () => {
  it('曜日は言語ごと（UTC で数える）', () => {
    expect(weekdayOf('2026-10-30', 'ja')).toBe('金')
    expect(weekdayOf('2026-10-30', 'en')).toBe('Fri')
    expect(weekdayOf('2026-10-26', 'ja')).toBe('月')
  })

  it('セクションの状態：記録なし・一部・すべて（おやつは数えない）', () => {
    const slot = (name: string, has: boolean) => ({
      slot: name,
      record: has
        ? { id: 1, value: '8', recorded_at: '2026-10-26T00:00:00Z', recorded_by_name: '田中' }
        : null,
      message_key: has ? null : NOT_RECORDED,
    })

    expect(sectionStatus({ item: 'meal', slots: [slot('breakfast', false)] })).toBe('unrecorded')
    expect(
      sectionStatus({ item: 'meal', slots: [slot('breakfast', true), slot('lunch', false)] }),
    ).toBe('partial')
    expect(
      sectionStatus({
        item: 'meal',
        slots: [slot('breakfast', true), slot('lunch', true), slot('dinner', true)],
      }),
    ).toBe('recorded')
    // おやつだけが記録されていて、ほかが未記録のときは、一部
    expect(
      sectionStatus({ item: 'meal', slots: [slot('lunch', false), slot('snack', true)] }),
    ).toBe('partial')
    // おやつが未記録でも、数えない
    expect(
      sectionStatus({ item: 'meal', slots: [slot('lunch', true), slot('snack', false)] }),
    ).toBe('recorded')
  })
})
