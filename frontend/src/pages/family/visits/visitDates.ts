// 面会の予約の画面（UI-F01）で使う、日付・時刻の計算と API の形（spec 003 の T012）。
// 日付は "YYYY-MM-DD" の文字のまま扱う（端末のタイムゾーンで 1 日ずれないように）。
// 予約できるかの最終の判定はバックエンドが日本時間で行う（research.md R-04）。ここは画面に並べる範囲を決めるだけ。

export type StartTime = { start_time: string; selectable: boolean } // "10:00:00"

export type Day = {
  date: string
  closed: boolean
  // この家族がもう予約している日（1 日 1 回まで）
  mine: boolean
  start_times: StartTime[]
}

export type Availability = { days: Day[] }

export type Reservation = {
  id: number
  visit_date: string
  start_time: string
  party_size: number
  status: string
}

// 予約できるのは、明日から 4 週間先まで（spec 003 FR-008）
export const BOOKABLE_DAYS = 28
// 1 組の面会の長さ（spec 003 FR-003）
export const VISIT_MINUTES = 90

/** 日本時間の今日（"YYYY-MM-DD"）。 */
export function todayInJapan(now: Date = new Date()): string {
  // en-CA は YYYY-MM-DD の形で出る
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo' }).format(now)
}

export function addDays(date: string, days: number): string {
  const value = new Date(`${date}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

/** 空きを読む範囲（明日から 28 日先まで）。 */
export function bookingRange(today: string): { from: string; to: string } {
  return { from: addDays(today, 1), to: addDays(today, BOOKABLE_DAYS) }
}

/** 曜日（0 が日曜日）。 */
export function weekdayOf(date: string): number {
  return new Date(`${date}T00:00:00Z`).getUTCDay()
}

export function monthDay(date: string): { month: number; day: number } {
  const [, month, day] = date.split('-').map(Number)
  return { month, day }
}

/** "10:00:00" → "10:00" */
export function hhmm(time: string): string {
  return time.slice(0, 5)
}

/** 開始時刻から 1 時間 30 分後の終わりの時刻（"10:00" → "11:30"）。 */
export function endOf(start: string): string {
  const [hour, minute] = start.split(':').map(Number)
  const total = hour * 60 + minute + VISIT_MINUTES
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

export type DayStatus = 'mine' | 'open' | 'full'

/** 日付のボタンの状態：予約済み／選べる時刻がある／空きなし（休みの日・締め切り後も「空きなし」）。 */
export function dayStatus(day: Day): DayStatus {
  if (day.mine) return 'mine'
  return !day.closed && day.start_times.some((slot) => slot.selectable) ? 'open' : 'full'
}

// --- 月ごとのカレンダー（docs/画面設計.md の UI-F01） ---

/** "2026-10-27" → "2026-10" */
export function monthOf(date: string): string {
  return date.slice(0, 7)
}

/** from〜to が入る月を、古い順に（明日〜28 日先なら 1 つか 2 つ）。 */
export function monthsBetween(from: string, to: string): string[] {
  const months: string[] = []
  let day = `${monthOf(from)}-01`
  while (monthOf(day) <= monthOf(to)) {
    months.push(monthOf(day))
    const [year, month] = monthOf(day).split('-').map(Number)
    day = month === 12 ? `${year + 1}-01-01` : `${year}-${String(month + 1).padStart(2, '0')}-01`
  }
  return months
}

/**
 * その月のカレンダーのマス（日〜土の 7 列）。月の外のマスは null。
 * 例："2026-10" は 1 日が木曜日なので、先頭に null が 4 つ並ぶ。
 */
export function calendarCells(month: string): (string | null)[] {
  const first = `${month}-01`
  const cells: (string | null)[] = Array.from({ length: weekdayOf(first) }, () => null)
  for (let day = first; monthOf(day) === month; day = addDays(day, 1)) cells.push(day)
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
}

// --- 自分の予約（003-T018） ---

/** `GET /api/family/visits` の 1 件（backend/app/api/family/visits.py の MyReservationOut）。 */
export type MyReservation = {
  id: number
  visit_date: string
  start_time: string // "10:00:00"
  party_size: number
  status: 'booked' | 'cancelled_by_family' | 'cancelled_by_staff'
  // 施設が取り消したときだけ入る理由
  cancel_reason: string | null
  // 今アプリで取り消せるか（予約済みで、前日 17 時より前。サーバーが日本時間で決める）
  can_cancel: boolean
}

export const MY_VISITS_KEY = ['family', 'visits', 'mine']
