// 家族のお知らせの一覧（UI-F04）の、API の形と、表示を決める部分（spec 001 の T061）。
// 画面（Notifications.tsx）と分けて、単体でテストできるようにしている。

/** `GET /api/family/notifications` の 1 件（backend/app/api/family/notifications.py）。 */
export type FamilyNotification = {
  id: number
  kind: string
  created_at: string
  read: boolean
  reply_id: number | null
  announcement_id: number | null
  period_start: string | null
  period_end: string | null
}

/** お知らせの種類ごとの、辞書のキー。知らない種類は、施設からのお知らせと同じ文言にする。 */
export function kindKey(kind: string): string {
  if (kind === 'reply' || kind === 'daily_digest' || kind === 'weekly_digest') {
    return `notifications.kind.${kind}`
  }
  return 'notifications.kind.announcement'
}

/**
 * 押したときに進む先。返事・まとめは連絡帳（返事のカードが出て、既読になる）。
 * 施設からのお知らせは、画面（作り込み）ができるまで、進む先がない。
 */
export function linkFor(notification: FamilyNotification): string | null {
  if (notification.kind === 'reply') return '/family'
  if (notification.kind === 'daily_digest' || notification.kind === 'weekly_digest')
    return '/family'
  return null
}
