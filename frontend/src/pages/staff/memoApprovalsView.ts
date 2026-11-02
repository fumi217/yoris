// 様子のメモの承認の画面（UI-S07。spec 007 の 007-T023）の形と、小さな部品。

/** `GET /api/staff/memo-approvals` の 1 件（backend/app/api/staff/memo_approvals.py の ApprovalOut）。 */
export type Approval = {
  id: number
  resident_id: number
  resident_name: string
  resident_name_ruby: string
  author_name: string
  // ログイン中の職員が書いたメモか。本人のメモには「承認する」「戻す」を出さない（FR-011a）
  is_own: boolean
  memo_date: string
  written_at: string
  source_lang: string
  original_text: string
  rewritten_text: string | null
  back_translation: string | null
  warnings: string[]
  status: string
  confirmed_at: string | null
  approved_at: string | null
  waiting_minutes: number | null
  overdue: boolean
}

export type ApprovalTab = 'pending' | 'approved'
export type ApprovalAction = 'approve' | 'return' | 'unpublish'

// 承認の API の一覧・件数のキャッシュのキー。承認・戻す・取り下げたあとに、まとめて取り直す。
// 承認待ちの件数（ゆうさんの 007-T028）も、この下に置いて、同じ取り直しで更新する
export const APPROVALS_KEY = ['staff', 'memo-approvals'] as const

// 戻す・公開を取り下げる理由の上限（backend の REASON_MAX）
export const REASON_MAX = 200

// 注意の印を、急ぎのものから並べる（急変・事故 → 医療 → ほかの入居者 → 長さ）。知らない印は出さない
const WARNING_ORDER = [
  'urgent_words',
  'medical_added',
  'medical_in_original',
  'other_name',
  'length_changed',
]

export function sortedWarnings(warnings: string[]): string[] {
  return WARNING_ORDER.filter((code) => warnings.includes(code))
}

/** 理由の文字数（絵文字なども 1 文字。backend の数え方と同じ）。 */
export function reasonLength(reason: string): number {
  return Array.from(reason.trim()).length
}

/** 理由として送れるか（1〜200 文字。前後の空白は数えない）。 */
export function isValidReason(reason: string): boolean {
  const length = reasonLength(reason)
  return length >= 1 && length <= REASON_MAX
}

/** 確かめてからの経過時間を、時間の単位で表す（0 なら 1 時間未満）。 */
export function waitingHours(minutes: number): number {
  return Math.floor(minutes / 60)
}

/** 日時（UTC）→ 日本時間の日付 "2026-10-26"。 */
export function jstDate(iso: string): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo' }).format(new Date(iso))
}
