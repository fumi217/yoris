// 家族の連絡帳（UI-F02）の、API の形と、表示を決める部分（spec 001 の T059）。
// 画面（ContactBook.tsx）と分けて、単体でテストできるようにしている。

/** `GET /api/family/contact-book` の 1 件の記録（backend/app/api/family/contact_book.py）。 */
export type ContactRecord = {
  id: number
  value: string
  recorded_at: string
  recorded_by_name: string
}

export type ContactSlot = {
  slot: string
  record: ContactRecord | null
  // 記録がないときだけ入る辞書のキー（「まだ記録されていません」）
  message_key: string | null
}

export type ContactSection = { item: string; slots: ContactSlot[] }

export type ContactReply = {
  id: number
  contact_book_date: string
  theme_code: string
  theme_emoji: string
  template_codes: string[]
  // 職員が書き足した文。辞書を通さず、文字としてだけ出す
  note: string | null
  replied_by_name: string
  // 職種のコード（辞書の occupation.*。#263）
  replied_by_occupation: string | null
  replied_at: string
  edited: boolean
  read: boolean
}

export type ContactBookData = {
  date: string
  unread_replies: ContactReply[]
  day_replies: ContactReply[]
  sections: ContactSection[]
}

/** 時刻を日本時間の "HH:MM" にする（端末のタイムゾーンに関わらず）。 */
export function timeInJapan(at: string): string {
  return new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(at))
}

/** 日本時間の今日（"2026-10-27"）。端末のタイムゾーンに関わらず、API の「今日」と同じ日にする。 */
export function todayInJapan(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo' }).format(now)
}

/** "2026-10-27" を days 日ずらす。UTC で数えるので、端末の時刻に左右されない。 */
export function shiftDate(date: string, days: number): string {
  const shifted = new Date(`${date}T00:00:00Z`)
  shifted.setUTCDate(shifted.getUTCDate() + days)
  return shifted.toISOString().slice(0, 10)
}

/**
 * URL の `?date=` を、見せる日にする。形が違う・実在しない日・今日より先は、今日にする
 * （記録がない日を API に送らない）。
 */
export function pickDate(value: string | null, today: string): string {
  if (value === null || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return today
  // 13 月・2 月 30 日のような、実在しない日は Date が無効か、別の日に直してしまう
  const parsed = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return today
  return value > today ? today : value
}

/** "2026-10-26" → { month: 10, day: 26 } */
export function monthDayOf(date: string): { month: number; day: number } {
  const [, month, day] = date.split('-').map(Number)
  return { month, day }
}

/** "2026-10-30" の曜日（言語ごと。日本語なら「金」）。UTC で数えるので、端末の時刻に左右されない。 */
export function weekdayOf(date: string, language: string): string {
  return new Intl.DateTimeFormat(language, { weekday: 'short', timeZone: 'UTC' }).format(
    new Date(`${date}T00:00:00Z`),
  )
}

export type SectionStatus = 'recorded' | 'partial' | 'unrecorded'

/**
 * セクション（食事・機嫌・眠り）の状態の印。おやつは毎日付けるとは限らないので、数えない（FR-017）。
 * 数える欄がすべて記録済み → recorded、1 つも記録がない → unrecorded、それ以外 → partial。
 */
export function sectionStatus(section: ContactSection): SectionStatus {
  if (!section.slots.some((slot) => slot.record !== null)) return 'unrecorded'
  const counted = section.slots.filter((slot) => slot.slot !== 'snack')
  return counted.every((slot) => slot.record !== null) ? 'recorded' : 'partial'
}

/** 食事は区分（朝・昼・夜・おやつ）の名前の辞書のキー。機嫌・眠りは 1 日 1 つなので、区分は出さない。 */
export function slotLabelKey(item: string, slot: string): string | null {
  return item === 'meal' ? `record.slot.${slot}` : null
}

export function itemKey(item: string): string {
  return `record.item.${item}`
}

export function valueKey(item: string, value: string): string {
  return `record.value.${item}.${value}`
}

/**
 * 既読を送るのは、返事 1 つにつき 1 回だけ。初めてなら true（送って、覚える）、2 回目からは false。
 * 画面に出入りしても、同じ返事の既読を重ねて送らない。
 */
export function markSentOnce(sent: Set<number>, replyId: number): boolean {
  if (sent.has(replyId)) return false
  sent.add(replyId)
  return true
}
