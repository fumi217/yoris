// 入居者一覧（UI-S01）の形と、行に並べる「記録済み／未記録」の目印（spec 001 の T031・docs/画面設計.md「4」）。

export const MEAL_SLOTS = ['breakfast', 'lunch', 'dinner', 'snack'] as const
export type MealSlot = (typeof MEAL_SLOTS)[number]

/** 入居者ごとの変化の目印（spec 006 の 006-T011。今の目印がなければ、行の change_flag は null）。 */
export type ChangeFlagMark = {
  has_flag: boolean
  // まだ確かめていない目印がある
  has_unconfirmed: boolean
}

/** `GET /api/staff/residents?date=` の 1 行（backend/app/api/staff/residents.py の ResidentRow）。 */
export type ResidentRow = {
  id: number
  display_name: string
  // ふりがな付きの名前（日本語の職員の画面だけ。それ以外は display_name と同じ）
  display_name_ruby: string
  room: string
  meals: Record<MealSlot, boolean>
  mood: boolean
  sleep: boolean
  waiting_requests: number
  waiting_messages: number
  change_flag: ChangeFlagMark | null
}

export type ResidentListResponse = {
  date: string // YYYY-MM-DD（日本時間の日付）
  residents: ResidentRow[]
  // まだ確かめていない目印がある入居者の人数（spec 006 の FR-003）
  unconfirmed_flag_count: number
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

/**
 * 一覧に並べる行（spec 006 の 006-T015・docs/画面設計.md「4」）。
 * 目印の付いた入居者を先に、その中も、ほかの入居者も、入居の順（API の順）のまま並べる。
 * onlyUnconfirmed のときは、まだ確かめていない目印のある入居者だけにする（件数と行数が一致する）。
 */
export function visibleRows(rows: ResidentRow[], onlyUnconfirmed: boolean): ResidentRow[] {
  const shown = onlyUnconfirmed ? rows.filter((row) => row.change_flag?.has_unconfirmed) : rows
  return [...shown.filter((row) => row.change_flag), ...shown.filter((row) => !row.change_flag)]
}

/**
 * 行に並べる記録のチップ（朝・昼・夜・機嫌・眠りの順。#431）。
 * おやつは、記録があるときだけ出す（まだでも出さず、目立たせない。毎日付けるとは限らないため。#187）。
 */
export function recordChips(row: ResidentRow): RecordMark[] {
  const meals = mealMarks(row).filter((mark) => !mark.optional || mark.recorded)
  return [...meals, ...dayMarks(row)]
}

/** 今日の記録の進み具合：記録した欄の数と、全部の欄の数（朝・昼・夜・機嫌・眠り。おやつは数えない）。 */
export function recordProgress(rows: ResidentRow[]): { recorded: number; total: number } {
  const required = (row: ResidentRow) => [
    row.meals.breakfast,
    row.meals.lunch,
    row.meals.dinner,
    row.mood,
    row.sleep,
  ]
  return rows.reduce(
    (sum, row) => ({
      recorded: sum.recorded + required(row).filter(Boolean).length,
      total: sum.total + required(row).length,
    }),
    { recorded: 0, total: 0 },
  )
}

/** 並べた行を、「気をつけたい人」（変化の目印がある）と、そのほかに分ける。順番はそのまま。 */
export function splitByFlag(rows: ResidentRow[]): {
  caution: ResidentRow[]
  others: ResidentRow[]
} {
  return {
    caution: rows.filter((row) => row.change_flag),
    others: rows.filter((row) => !row.change_flag),
  }
}

/**
 * 「気をつけたい人」の面を出すか。目印のある人がいる・確かめていない目印がある、のどちらかのとき。
 * 絞り込み中は、件数が 0 になっても出す（出さないと、絞り込みを戻すボタンも消えて、一覧が空のまま戻せない。#432）。
 */
export function showCautionSection(
  cautionCount: number,
  unconfirmedFlagCount: number,
  onlyUnconfirmed: boolean,
): boolean {
  return cautionCount > 0 || unconfirmedFlagCount > 0 || onlyUnconfirmed
}
