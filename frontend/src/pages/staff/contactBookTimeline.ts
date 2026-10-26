// 職員の連絡帳の見返し（UI-S04）で、記録と返事を 1 本の時刻の並びにする（spec 001 の T033・FR-024）。

import type { StaffContactBook, StaffRecord, StaffReply } from './recordValues'

export type TimelineEntry =
  | { kind: 'record'; at: string; record: StaffRecord }
  | { kind: 'reply'; at: string; reply: StaffReply }

/** 記録と返事を、時刻の古い順に 1 本にする（同じ時刻なら記録が先）。 */
export function timeline(book: StaffContactBook): TimelineEntry[] {
  const entries: TimelineEntry[] = [
    ...book.records.map((record) => ({ kind: 'record' as const, at: record.recorded_at, record })),
    ...book.replies.map((reply) => ({ kind: 'reply' as const, at: reply.replied_at, reply })),
  ]
  return entries.sort((a, b) => Date.parse(a.at) - Date.parse(b.at))
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

/** 記録の項目・区分の辞書のキー（食事は区分ごと、機嫌・眠りは項目の名前）。 */
export function recordLabelKey(record: StaffRecord): string {
  return record.item === 'meal' ? `record_page.slot.${record.slot}` : `record.item.${record.item}`
}

/** "YYYY-MM-DD" の日付を n 日ずらす（文字のまま。端末のタイムゾーンでずれない）。 */
export function shiftDate(date: string, days: number): string {
  const value = new Date(`${date}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}
