// 入居者一覧（UI-S01）の形と、行に並べる「記録済み／未記録」の目印（spec 001 の T031・docs/画面設計.md「4」）。

export const MEAL_SLOTS = ['breakfast', 'lunch', 'dinner', 'snack'] as const
export type MealSlot = (typeof MEAL_SLOTS)[number]

/** `GET /api/staff/residents?date=` の 1 行（backend/app/api/staff/residents.py の ResidentRow）。 */
export type ResidentRow = {
  id: number
  display_name: string
  room: string
  meals: Record<MealSlot, boolean>
  mood: boolean
  sleep: boolean
  waiting_requests: number
  waiting_messages: number
}

export type ResidentListResponse = {
  date: string // YYYY-MM-DD（日本時間の日付）
  residents: ResidentRow[]
}

export type RecordMark = {
  labelKey: string
  recorded: boolean
  // まだでも目立たせない（おやつは毎日付けるとは限らないので、記録し忘れに見せない。PR #187 みさき）
  optional?: boolean
}

/** 食事の区分の目印（朝・昼・夜・おやつの順）。 */
export function mealMarks(row: ResidentRow): RecordMark[] {
  return MEAL_SLOTS.map((slot) => ({
    labelKey: `record.slot.${slot}`,
    recorded: row.meals[slot],
    optional: slot === 'snack',
  }))
}

/** 機嫌・眠りの目印（1 日 1 つ）。 */
export function dayMarks(row: ResidentRow): RecordMark[] {
  return [
    { labelKey: 'record.item.mood', recorded: row.mood },
    { labelKey: 'record.item.sleep', recorded: row.sleep },
  ]
}

/** 一覧の上に出す、家族からのメッセージの対応待ちの合計。 */
export function totalWaitingMessages(rows: ResidentRow[]): number {
  return rows.reduce((sum, row) => sum + row.waiting_messages, 0)
}

/** "2026-10-26" → { month: 10, day: 26 }（タイムゾーンで日付がずれないよう、文字のまま分ける）。 */
export function monthDay(date: string): { month: number; day: number } {
  const [, month, day] = date.split('-').map(Number)
  return { month, day }
}
