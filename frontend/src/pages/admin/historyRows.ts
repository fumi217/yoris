// 開示設定の変更履歴（spec 001 の T041・FR-011）の形と、表示に使う値。

/** `GET /api/admin/disclosure/history` の 1 件（backend/app/api/admin/disclosure.py の HistoryOut）。 */
export type DisclosureHistoryRow = {
  id: number
  target_type: 'item' | 'theme'
  target_code: string
  old_visible: boolean
  new_visible: boolean
  changed_by_name: string
  changed_at: string
}

export const HISTORY_QUERY_KEY = ['admin', 'disclosure', 'history']

/** 何を変えたかの辞書のキー（記録の項目は disclosure.item.*、テーマはそのコード）。 */
export function targetLabelKey(row: DisclosureHistoryRow): string {
  return row.target_type === 'item' ? `disclosure.item.${row.target_code}` : row.target_code
}

/** 変えた日時を、日本時間の月・日・時刻に分ける（端末のタイムゾーンに関わらず）。 */
export function changedAtParts(at: string): { month: number; day: number; time: string } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Tokyo',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(at))
  const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return {
    month: Number(pick('month')),
    day: Number(pick('day')),
    time: `${pick('hour')}:${pick('minute')}`,
  }
}
