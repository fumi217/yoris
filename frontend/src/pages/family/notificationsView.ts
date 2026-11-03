// 家族のお知らせの一覧（UI-F04）の、API の形と、表示を決める部分（spec 001 の T061）。
// 画面（Notifications.tsx）と分けて、単体でテストできるようにしている。

import type { IconName } from '../../components/Icon'

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
  // まとめに入った様子のメモの書いた日（古い順。書いた日の連絡帳へのリンクに使う。中身は来ない）
  memo_dates: string[]
  // まとめ（daily_digest・weekly_digest）に、写真・記録が含まれるか（spec 005 の FR-018）
  has_album: boolean
  has_records: boolean
}

/** お知らせの種類ごとの、辞書のキー。知らない種類は、施設からのお知らせと同じ文言にする。 */
export function kindKey(kind: string): string {
  if (
    kind === 'reply' ||
    kind === 'daily_digest' ||
    kind === 'weekly_digest' ||
    kind === 'staff_message_reply' ||
    kind === 'visit_confirmed' ||
    kind === 'visit_cancelled' ||
    kind === 'visit_reminder'
  ) {
    return `notifications.kind.${kind}`
  }
  return 'notifications.kind.announcement'
}

/** 写真が含まれるまとめか（記録だけのまとめ・まとめ以外は false）。 */
function hasAlbum(notification: FamilyNotification): boolean {
  return (
    (notification.kind === 'daily_digest' || notification.kind === 'weekly_digest') &&
    notification.has_album
  )
}

/**
 * 写真だけのまとめか（写真が含まれ、記録も様子のメモもない）。文言と進む先の両方が、これで決まる。
 * 様子のメモが入るまとめは、メモの書いた日の連絡帳へのリンクがあるので、写真だけにしない（spec 007）。
 */
function isAlbumOnly(notification: FamilyNotification): boolean {
  return hasAlbum(notification) && !notification.has_records && notification.memo_dates.length === 0
}

/**
 * 一覧に出す文言の辞書のキー。まとめは、記録だけ・写真だけ・両方の 3 通りから選ぶ
 * （写真だけは `_album`、記録かメモと写真の両方は `_with_album`）。まとめ以外は `kindKey` と同じ。
 */
export function noticeKey(notification: FamilyNotification): string {
  const base = kindKey(notification.kind)
  if (!hasAlbum(notification)) return base
  return isAlbumOnly(notification) ? `${base}_album` : `${base}_with_album`
}

/**
 * 押したときに進む先。返事・まとめは連絡帳（返事のカードが出て、既読になる）。
 * 職員の返事（問い合わせ AI のメッセージへの返事）は「お問い合わせ」の画面（返事の発言が出て、既読になる）。
 * 面会のお知らせ（確定・取り消し・前日の知らせ）は、面会の画面。
 * 施設からのお知らせは、画面（作り込み）ができるまで、進む先がない。
 * 写真だけのまとめ（記録もメモもない）は、見る場所がアルバムなので、アルバムへ進む。
 */
export function linkFor(notification: FamilyNotification): string | null {
  if (notification.kind === 'reply') return '/family'
  if (notification.kind === 'daily_digest' || notification.kind === 'weekly_digest')
    return isAlbumOnly(notification) ? '/family/album' : '/family'
  if (notification.kind === 'staff_message_reply') return '/family/inquiry'
  if (
    notification.kind === 'visit_confirmed' ||
    notification.kind === 'visit_cancelled' ||
    notification.kind === 'visit_reminder'
  )
    return '/family/visits'
  return null
}

/**
 * お知らせの種類ごとの、アイコン（デザインの決めごと 14.2）。まとめは連絡帳、職員の返事は「お問い合わせ」、
 * 面会の前日の知らせは「面会予約」と同じアイコン。知らない種類は、施設からのお知らせと同じ。
 */
export function noticeIconName(kind: string): IconName {
  switch (kind) {
    case 'reply':
      return 'notice-reply'
    case 'daily_digest':
    case 'weekly_digest':
      return 'contact-book'
    case 'staff_message_reply':
      return 'inquiry'
    case 'visit_confirmed':
      return 'notice-visit-confirmed'
    case 'visit_cancelled':
      return 'notice-visit-cancelled'
    case 'visit_reminder':
      return 'visits'
    default:
      return 'notice-announcement'
  }
}

/** まだ読んでいないお知らせの数（上の「未読 ◯ 件」。0 件のときは出さない）。 */
export function unreadCount(notifications: FamilyNotification[]): number {
  return notifications.filter((notification) => !notification.read).length
}

/** 日本時間の日付（"2026-10-30"）。端末の時刻帯に左右されない。 */
export function jstDateOf(date: Date): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return `${pick('year')}-${pick('month')}-${pick('day')}`
}

/** 見出しの種類：今日・昨日・それ以外の日（日付と曜日）。 */
export type DayKind = 'today' | 'yesterday' | 'other'

export type DayGroup = {
  // 日本時間の日付（"2026-10-30"）
  date: string
  kind: DayKind
  items: FamilyNotification[]
}

/**
 * お知らせを、日本時間の日ごとにまとめる。順番は、API が返した順（新しい順）のまま。
 * now はテスト用（今日・昨日の判定に使う）。
 */
export function groupByDay(
  notifications: FamilyNotification[],
  now: Date = new Date(),
): DayGroup[] {
  const today = jstDateOf(now)
  const yesterday = jstDateOf(new Date(now.getTime() - 24 * 60 * 60 * 1000))
  const groups: DayGroup[] = []
  for (const notification of notifications) {
    const date = jstDateOf(new Date(notification.created_at))
    const last = groups[groups.length - 1]
    if (last && last.date === date) {
      last.items.push(notification)
      continue
    }
    const kind: DayKind = date === today ? 'today' : date === yesterday ? 'yesterday' : 'other'
    groups.push({ date, kind, items: [notification] })
  }
  return groups
}

/** 様子のメモの書いた日の連絡帳へ進む先（spec 007 の FR-012b）。 */
export function memoDateLink(date: string): string {
  return `/family?date=${date}`
}
