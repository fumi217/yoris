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

/** "2026-10-26" → { month: 10, day: 26 } */
export function monthDayOf(date: string): { month: number; day: number } {
  const [, month, day] = date.split('-').map(Number)
  return { month, day }
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
