// 変化の目印の形と、文を組み立てる部品（spec 006 の 006-T006・T013・T018。research.md R-06）。
// API は文言を返さず、決まりのコードともとの記録のコードだけを返す。文は画面が辞書から組み立てる。

/** もとになった記録の 1 件（`GET /api/staff/residents/{id}/change-flags` の evidence）。 */
export type Evidence = { record_id: number; date: string; slot: string; value: string }

/** 確かめた記録の 1 件。確かめた職員は表示名だけを返す。note は職員が書いたまま。 */
export type Confirmation = {
  staff_display_name: string
  confirmed_at: string
  note: string | null
}

/** 目印の 1 件（contracts/api.md）。history の分には cleared_at・cleared_reason も付く。 */
export type ChangeFlag = {
  id: number
  rule_code: string
  started_at: string
  streak: number
  evidence: Evidence[]
  status: 'unconfirmed' | 'confirmed' | 'cleared'
  cleared_at?: string | null
  cleared_reason?: string | null
  confirmations: Confirmation[]
}

export type ChangeFlags = { current: ChangeFlag[]; history: ChangeFlag[] }

// ひとことの上限（backend の確かめる API と同じ。FR-009）
export const NOTE_MAX = 100

// 決まりのコード → もとになる記録の項目（辞書の record.item.* ・ record.value.<項目>.* を引く）
const RULE_ITEMS: Record<string, 'meal' | 'mood' | 'sleep'> = {
  meal_low: 'meal',
  mood_low: 'mood',
  sleep_poor: 'sleep',
}

/** 決まりのコードから記録の項目を返す。知らない決まり（あとで足した決まりなど）は undefined。 */
export function itemOf(ruleCode: string): 'meal' | 'mood' | 'sleep' | undefined {
  return RULE_ITEMS[ruleCode]
}

/** 画面に出せる目印か（知らない決まりや、もとの記録のない目印は出せない）。 */
export function isShown(flag: ChangeFlag): boolean {
  return itemOf(flag.rule_code) !== undefined && flag.evidence.length > 0
}

/** もとの記録を、日付の古い順に並べる（API の順に頼らない）。 */
export function sortedEvidence(evidence: Evidence[]): Evidence[] {
  return [...evidence].sort((a, b) => a.date.localeCompare(b.date))
}

/** "2026-10-26" → { month: 10, day: 26 }（タイムゾーンで日付がずれないよう、文字のまま分ける）。 */
export function monthDay(date: string): { month: number; day: number } {
  const [, month, day] = date.split('-').map(Number)
  return { month, day }
}

/** 日時（UTC）→ 日本時間の日付 "2026-10-26"。 */
export function jstDate(iso: string): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo' }).format(new Date(iso))
}

/** ひとこと の文字数（絵文字なども 1 文字。backend の数え方と同じ）。 */
export function noteLength(note: string): number {
  return Array.from(note).length
}

/** まだ確かめていない目印があるか（「確かめた」ボタンを出すか）。 */
export function hasUnconfirmed(current: ChangeFlag[]): boolean {
  return current.some((flag) => flag.status === 'unconfirmed')
}

/** 確かめる API に送る内容。空白だけのひとことは送らない。 */
export function confirmBody(note: string): { note?: string } {
  const trimmed = note.trim()
  return trimmed === '' ? {} : { note: trimmed }
}
