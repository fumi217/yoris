// 面会の予約の一覧（UI-S11）と今日の面会予定（UI-S12）の、API の形と並べ方（spec 003 の T026・T027・T031）。
// 画面と分けて、単体でテストできるようにしている。

import { addDays, BOOKABLE_DAYS } from '../family/visits/visitDates'

/** 予約 1 件（backend/app/api/admin/visits.py の StaffReservationOut）。呼び名・理由は文字としてだけ出す。 */
export type StaffReservation = {
  id: number
  visit_date: string
  start_time: string // "10:00:00"
  resident_id: number
  resident_name: string
  room: string
  party_size: number
  status: 'booked' | 'cancelled_by_family' | 'cancelled_by_staff'
  created_at: string // 予約した日時
  cancel_reason: string | null
}

// 予約の一覧と今日の予定のキー。休みの日にしたとき（面会の設定の画面）も、これを読み直す
export const VISITS_KEY = ['admin', 'visits'] as const
export const TODAY_VISITS_KEY = [...VISITS_KEY, 'today'] as const

/**
 * 一覧を読む範囲：今日から、家族が予約できるいちばん先の日（4 週間先）まで。
 * API の上限（31 日）に収まる。
 */
export function listRange(today: string): { from: string; to: string } {
  return { from: today, to: addDays(today, BOOKABLE_DAYS) }
}

/** 日付ごとにまとめる（API の並び＝日時の順のまま）。 */
export function groupByDate(
  rows: StaffReservation[],
): { date: string; rows: StaffReservation[] }[] {
  const groups: { date: string; rows: StaffReservation[] }[] = []
  for (const row of rows) {
    const last = groups.at(-1)
    if (last && last.date === row.visit_date) last.rows.push(row)
    else groups.push({ date: row.visit_date, rows: [row] })
  }
  return groups
}

/** 今日の面会の組数（予約済みだけ）。 */
export function bookedCount(rows: StaffReservation[]): number {
  return rows.filter((row) => row.status === 'booked').length
}

/**
 * 一覧を開いた側（職員の画面・管理画面）。家族からのメッセージ（messagesBase）と同じ考え方で、
 * 戻り先やリンクを、開いた側にそろえる。
 */
export function visitsBase(pathname: string): '/staff/visits' | '/admin/visits' {
  return pathname.startsWith('/admin') ? '/admin/visits' : '/staff/visits'
}
