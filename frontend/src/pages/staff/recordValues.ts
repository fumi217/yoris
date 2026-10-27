// 記録の画面（UI-S02）で押せる値と、今付いている値の探し方（spec 001 の T032・docs/画面設計.md「5」）。
// 値のコードは backend/app/models/records.py の VALUES と同じ。文言は辞書の record.value.*。

import type { StaffRole } from '../../auth/me'
import { MEAL_SLOTS, type MealSlot } from './residentRows'

export type Item = 'meal' | 'mood' | 'sleep'

export const VALUES: Record<Item, readonly string[]> = {
  // 全部・ほぼ全部・半分・少し・食べていない・食事なし（外泊・入院など）
  meal: ['10', '8', '5', '2', '0', 'none'],
  // 笑顔が多い・いつもどおり・元気がない
  mood: ['smile', 'normal', 'low'],
  // よく眠れた・いつもどおり・あまり眠れなかった
  sleep: ['good', 'normal', 'poor'],
}

// 機嫌・眠りは 1 日 1 つ
export const DAY_SLOT = 'day'

/** `GET /api/staff/residents/{id}/contact-book` の記録 1 件。 */
export type StaffRecord = {
  id: number
  item: Item
  slot: string
  value: string
  recorded_at: string
  recorded_by_name: string
}

export type StaffReply = {
  id: number
  request_id: number
  theme_code: string
  theme_emoji: string
  template_codes: string[]
  note: string | null
  replied_by_name: string
  replied_at: string
  edited: boolean
  read: boolean
  // 直すための値（001-T063）：選んだ定型文の id、そのテーマの定型文、今日直せるか
  template_ids: number[]
  template_options: { id: number; code: string }[]
  editable: boolean
}

export type StaffContactBook = {
  date: string // YYYY-MM-DD（日本時間）
  resident: { id: number; display_name: string; room: string }
  records: StaffRecord[]
  replies: StaffReply[]
}

/** その項目・区分に今付いている記録。なければ null。 */
export function currentRecord(
  records: StaffRecord[],
  item: Item,
  slot: string,
): StaffRecord | null {
  return records.find((record) => record.item === item && record.slot === slot) ?? null
}

/** その項目・区分に今付いている値。なければ null。 */
export function currentValue(records: StaffRecord[], item: Item, slot: string): string | null {
  return currentRecord(records, item, slot)?.value ?? null
}

/** 最初に開いておく食事の区分：まだ記録していない最初の区分（全部付いていれば朝ごはん）。 */
export function firstUnrecordedMealSlot(records: StaffRecord[]): MealSlot {
  return MEAL_SLOTS.find((slot) => currentValue(records, 'meal', slot) === null) ?? MEAL_SLOTS[0]
}

/** 保存できた記録で、その項目・区分の記録を置き換える（押し直しは上書き）。 */
export function withRecord(book: StaffContactBook, record: StaffRecord): StaffContactBook {
  const others = book.records.filter(
    (other) => !(other.item === record.item && other.slot === record.slot),
  )
  return { ...book, records: [...others, record] }
}

/**
 * 「様子のメモを書く」を出す役割（spec 007 の T012）。メモを書く API が介護職員・リーダーだけのため、
 * ほかの役割には出さない（押しても 403 になるだけ。docs/画面設計.md の「5」の 4）。
 */
export function canWriteMemo(role: StaffRole | null | undefined): boolean {
  return role === 'care_worker' || role === 'leader'
}

/** 取り消した記録を外す（001-T034）。 */
export function withoutRecord(book: StaffContactBook, recordId: number): StaffContactBook {
  return { ...book, records: book.records.filter((record) => record.id !== recordId) }
}
