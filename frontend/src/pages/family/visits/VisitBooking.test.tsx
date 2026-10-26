import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../../i18n'
import { BookingView } from './VisitBooking'
import {
  addDays,
  bookingRange,
  dayStatus,
  endOf,
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

describe('BookingView', () => {
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

  it('予約できなかったら、理由を出す', () => {
    expect(render({ errorKey: 'error.visit_overlap' })).toContain('ほかの予約と重なっています')
  })
})
