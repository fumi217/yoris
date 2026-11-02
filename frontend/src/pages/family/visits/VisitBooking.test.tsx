import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../../i18n'
import { FuriganaContext } from '../../../i18n/furigana'
import { BookingView } from './VisitBooking'
import {
  addDays,
  bookingRange,
  calendarCells,
  dayStatus,
  endOf,
  monthsBetween,
  todayInJapan,
  weekdayOf,
  type Day,
  type Reservation,
} from './visitDates'

const day = (overrides: Partial<Day> = {}): Day => ({
  date: '2026-10-27',
  closed: false,
  mine: false,
  start_times: [
    { start_time: '10:00:00', selectable: true },
    { start_time: '10:30:00', selectable: false },
  ],
  ...overrides,
})

const render = (props: Partial<Parameters<typeof BookingView>[0]> = {}) =>
  renderToStaticMarkup(
    <BookingView
      days={[day()]}
      booking={false}
      confirmed={null}
      errorKey={null}
      onBook={() => {}}
      onReset={() => {}}
      {...props}
    />,
  )

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('visitDates', () => {
  it('今日は日本時間で決める', () => {
    // 日本時間では 10/27 の 0 時台（UTC ではまだ 10/26）
    expect(todayInJapan(new Date('2026-10-26T15:30:00Z'))).toBe('2026-10-27')
  })

  it('空きを読むのは、明日から 28 日先まで', () => {
    expect(bookingRange('2026-10-26')).toEqual({ from: '2026-10-27', to: '2026-11-23' })
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })

  it('面会は 1 時間 30 分', () => {
    expect(endOf('10:00')).toBe('11:30')
    expect(endOf('15:30')).toBe('17:00')
  })

  it('曜日を文字のまま決める', () => {
    expect(weekdayOf('2026-10-26')).toBe(1) // 月曜日
  })

  it('予約済みの日・選べる時刻がない日は、日付を押せない', () => {
    expect(dayStatus(day())).toBe('open')
    expect(dayStatus(day({ mine: true }))).toBe('mine')
    expect(dayStatus(day({ start_times: [{ start_time: '10:00:00', selectable: false }] }))).toBe(
      'full',
    )
    expect(dayStatus(day({ closed: true }))).toBe('full')
  })
})

describe('calendar', () => {
  it('月のマスは日〜土の 7 列。1 日の曜日まで空ける', () => {
    const cells = calendarCells('2026-10') // 10/1 は木曜日

    expect(cells.slice(0, 5)).toEqual([null, null, null, null, '2026-10-01'])
    expect(cells.length % 7).toBe(0)
    expect(cells.filter(Boolean)).toHaveLength(31)
  })

  it('予約できる期間が次の月にかかれば、月は 2 つ', () => {
    expect(monthsBetween('2026-10-27', '2026-11-23')).toEqual(['2026-10', '2026-11'])
    expect(monthsBetween('2026-11-02', '2026-11-29')).toEqual(['2026-11'])
    expect(monthsBetween('2026-12-20', '2027-01-16')).toEqual(['2026-12', '2027-01'])
  })
})

describe('BookingView', () => {
  it('期間が次の月にかかるときだけ、「次の月」を押せる（矢印のボタン。名前は aria-label）', () => {
    const next = (html: string) => html.match(/<button[^>]*aria-label="次の月"[^>]*>/)?.[0] ?? ''

    expect(next(render())).toContain('disabled=""')
    expect(next(render({ days: [day(), day({ date: '2026-11-02' })] }))).not.toContain(
      'disabled=""',
    )
    expect(render()).toContain('data-icon="chevron-right"')
  })

  it('期間の外の日は、押せるボタンにしない', () => {
    const html = render()

    // 10/27 だけがボタン。10/26 などは数字だけ
    expect(html).toContain('aria-label="10月27日（火）"')
    expect(html).not.toContain('aria-label="10月26日')
  })

  it('selectable: false の開始時刻は押せない', () => {
    const html = render({ initialDate: '2026-10-27' })

    expect(html).toMatch(/<button[^>]*>10:00〜11:30<\/button>/)
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>10:30〜12:00<\/button>/)
    expect(html).not.toMatch(/<button[^>]*disabled=""[^>]*>10:00〜11:30<\/button>/)
  })

  it('mine: true の日は「予約済み」と出て、押せない', () => {
    const html = render({ days: [day({ mine: true })] })

    expect(html).toContain('予約済')
    expect(html).toMatch(/<button[^>]*disabled=""/)
  })

  it('日付を選ぶまでは、時刻・人数・「予約する」を出さない', () => {
    const html = render()

    expect(html).not.toContain('10:00〜11:30')
    expect(html).not.toContain('予約</ruby>する')
  })

  it('確定したら、日時・人数とともに「予約が確定しました」と出す', () => {
    const confirmed: Reservation = {
      id: 1,
      visit_date: '2026-10-27',
      start_time: '13:00:00',
      party_size: 2,
      status: 'booked',
    }
    const html = render({ confirmed })

    expect(html).toContain('確定')
    expect(html).toContain('13:00〜14:30')
    expect(html).toContain('10<ruby>月')
    expect(html).toContain('2<ruby>人')
  })

  it('予約できなかったら、理由を出す（家族の画面なので、ふりがななし）', () => {
    const html = renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <BookingView
          days={[day()]}
          booking={false}
          confirmed={null}
          errorKey="error.visit_overlap"
          onBook={() => {}}
          onReset={() => {}}
        />
      </FuriganaContext.Provider>,
    )

    expect(html).toContain('ほかの予約と重なっています')
  })

  it('手順は 3 つの面に分け、丸い番号を付ける（日にち → 時刻 → 人数）。人数は、時刻を選んでから出す', () => {
    const date = render({ initialDate: '2026-10-27' })

    expect(text(date)).toContain('日にちを選んでください')
    expect(text(date)).toContain('面会開始時刻を選んでください')
    expect(text(date)).not.toContain('来館者の人数')
    expect(date.match(/<section aria-labelledby="visit-step-/g)).toHaveLength(2)
    expect(date).toMatch(/<span aria-hidden="true"[^>]*>1<\/span>/)
    expect(date).toMatch(/<span aria-hidden="true"[^>]*>2<\/span>/)
  })

  it('説明（1 回 1 時間 30 分・前日 17 時まで）は、薄い青の案内の帯に、アイコンつきで出す', () => {
    const html = render()

    expect(html).toMatch(
      /<p class="[^"]*bg-primary-soft[^"]*"[^>]*><svg[^>]*data-icon="circle-info"/,
    )
    expect(text(html)).toContain('1時間30分')
  })

  it('カレンダーは、選んだ日を青の塗り、予約済みを薄い青、空きなしをグレーで見分け、文字も添える', () => {
    const html = render({
      days: [
        day({ date: '2026-10-27' }),
        day({ date: '2026-10-28', mine: true }),
        day({ date: '2026-10-29', closed: true }),
      ],
      initialDate: '2026-10-27',
    })

    expect(html).toMatch(
      /<button[^>]*aria-label="10月27日（火）"[^>]*class="[^"]*bg-primary [^"]*shadow-md/,
    )
    expect(html).toMatch(/<button[^>]*aria-label="10月28日（水）"[^>]*class="[^"]*bg-primary-soft/)
    expect(html).toMatch(/<button[^>]*aria-label="10月29日（木）"[^>]*class="[^"]*bg-page/)
    expect(text(html)).toContain('予約済み')
    expect(text(html)).toContain('空きなし')
    // 見分けの見本（凡例）
    expect(text(html)).toContain('選べる')
  })

  it('日付を選んだだけでは、「予約する」のボタンと、選んだ内容の 1 行は出さない（時刻を選んでから）', () => {
    const html = render({ initialDate: '2026-10-27' })

    expect(html).not.toContain('data-icon="check"')
  })

  it('確定のあとは、緑のチェックの丸と、前の日の知らせの一言を出す', () => {
    const confirmed: Reservation = {
      id: 1,
      visit_date: '2026-10-27',
      start_time: '13:00:00',
      party_size: 2,
      status: 'booked',
    }
    const html = render({ confirmed })

    expect(html).toContain('data-icon="check"')
    expect(html).toContain('bg-[#dcfce7]')
    expect(text(html)).toContain('前の日の 20時に、あらためてお知らせします')
    expect(text(html)).toContain('ほかの日を見る')
  })

  it('手順 3 の見出しは、「〜を選んでください」の形。手順 2 の選んだ日付は、見出しの下に出す', () => {
    const html = render({ initialDate: '2026-10-27' })

    expect(text(html)).toContain('面会開始時刻を選んでください')
    // 日付は、見出し（h2）の中ではなく、その下の段落
    expect(html).toMatch(/<\/h2><\/div><p class="[^"]*ml-\[2\.125rem\][^"]*">/)
  })

  it('カレンダーのマスの中の「予約／済み」「空き／なし」は 12px（text-xs）で、マスの高さは 56px（min-h-14）', () => {
    const html = render({
      days: [day({ date: '2026-10-27', mine: true }), day({ date: '2026-10-28', closed: true })],
    })

    expect(html).toMatch(/<span class="block text-xs[^"]*whitespace-pre-line">/)
    expect(html).not.toContain('text-[0.6rem]')
    expect(html).toContain('min-h-14')
  })
})
