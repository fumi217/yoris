// 面会の設定の画面（UI-A02。spec 003 の T025）の、API の形と、選べる値・確かめの決まり。
// 画面（VisitSettings.tsx）と分けて、単体でテストできるようにしている。
// 最終の判定はバックエンド（backend/app/services/visits.py の _check_candidate など）が行う。

import { ApiError } from '../../api/client'
import { addDays } from '../family/visits/visitDates'

export type VisitSettingsData = {
  daily_limit: number
  start_times: string[] // "10:00:00"（早い順）
}

export type ClosedDay = { id: number; closed_date: string }

export type ClosedDayResult = ClosedDay & {
  // 休みにするために取り消した予約の数
  cancelled: number
}

// 開始時刻の候補に選べる時刻：30 分刻み、10:00 から、終わり（＋1 時間 30 分）が 17:00 まで（FR-009）
export const CANDIDATE_TIMES: readonly string[] = Array.from({ length: 12 }, (_, index) => {
  const minutes = 10 * 60 + index * 30
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${minutes % 60 === 0 ? '00' : '30'}:00`
})

// 1 日に受け付ける組数の範囲（下限は backend と同じ 1。上限は候補の数より多くは要らないため）
export const DAILY_LIMIT_MIN = 1
export const DAILY_LIMIT_MAX = CANDIDATE_TIMES.length

// 取り消しの理由の文字数の上限（backend の CANCEL_REASON_MAX）
export const REASON_MAX = 200

// 休みの日の一覧を読む範囲（今日から 1 年先まで）
export const CLOSED_DAYS_AHEAD = 365

/** 時刻を選ぶ・外す。いつも早い順にする。 */
export function toggleTime(selected: readonly string[], time: string): string[] {
  const next = selected.includes(time)
    ? selected.filter((value) => value !== time)
    : [...selected, time]
  return next.sort()
}

/** 組数を範囲の中に収める。 */
export function clampDailyLimit(value: number): number {
  return Math.min(DAILY_LIMIT_MAX, Math.max(DAILY_LIMIT_MIN, value))
}

/** 休みの日の一覧を読む範囲（今日から）。 */
export function closedDaysRange(today: string): { from: string; to: string } {
  return { from: today, to: addDays(today, CLOSED_DAYS_AHEAD) }
}

/**
 * 休みにしようとした日に予約が入っていたとき（409 `visit_day_has_reservations`）、その件数。
 * ほかのエラーなら null。
 */
export function reservationCountOf(error: unknown): number | null {
  if (!(error instanceof ApiError) || error.code !== 'visit_day_has_reservations') return null
  const count = error.details.count
  return typeof count === 'number' ? count : null
}

/** 取り消しの理由を送れない理由。送れるなら null（前後の空白は数えない。backend と同じ）。 */
export function reasonProblem(reason: string): 'empty' | 'too_long' | null {
  const length = Array.from(reason.trim()).length
  if (length === 0) return 'empty'
  if (length > REASON_MAX) return 'too_long'
  return null
}
