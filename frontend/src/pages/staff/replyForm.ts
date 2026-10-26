// 職員の返事の画面（UI-S03）の形と、定型文の選び方・書き足しの数え方（spec 001 の T062・FR-030）。

/** `GET /api/staff/residents/{id}/requests` の 1 件（backend/app/api/staff/requests.py）。 */
export type WaitingRequest = {
  id: number
  theme_code: string
  theme_emoji: string
  created_at: string
  days: number // 送られてからの日数（日本時間の日付で数える）
  templates: { id: number; code: string }[]
}

export type WaitingRequests = { requests: WaitingRequest[]; waiting_messages: number }

// 書き足しの上限（backend の MAX_NOTE_LENGTH）
export const MAX_NOTE_LENGTH = 100

/** 定型文を選ぶ／外す。選んだ順に並べる（家族の画面にもこの順で出る）。 */
export function toggleTemplate(selected: number[], id: number): number[] {
  return selected.includes(id) ? selected.filter((other) => other !== id) : [...selected, id]
}

/** 書き足しの文字数（絵文字なども 1 文字。backend の数え方と同じ）。 */
export function noteLength(note: string): number {
  return Array.from(note).length
}

/** 送る内容。空白だけの書き足しは送らない。 */
export function replyBody(templateIds: number[], note: string) {
  const trimmed = note.trim()
  return { template_ids: templateIds, note: trimmed === '' ? null : trimmed }
}
