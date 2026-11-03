import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import mascotFace from '../../assets/brand/mascot-normal.png'
import { Icon } from '../../components/Icon'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { weekdayOf } from './contactBookView'
import {
  groupByDay,
  linkFor,
  memoDateLink,
  noticeIconName,
  noticeKey,
  unreadCount,
  type DayGroup,
  type FamilyNotification,
} from './notificationsView'
import { sentAtParts } from './requestsView'

const NOTIFICATIONS_KEY = ['family', 'notifications'] as const

/**
 * 家族のお知らせの一覧（UI-F04。spec 001 の T061）。`/family/notifications`
 * 届いたお知らせ（返事・まとめ・施設からのお知らせ）を新しい順に出す。まだ読んでいないものは印をつける。
 * 一覧に返事の中身は出さない（API が返さない。中身は連絡帳で見る。SC-010）。
 * 返事のお知らせは、連絡帳で返事を読んだときに既読になる（001-T056）。
 * 1 つもないときは、キャラクターとやわらかい一言を出す（デザインの決めごと 13 章。#350）。
 * 見た目（#399）：上に「未読 ◯ 件」、日ごとの見出しでまとめ、1 つの白い面の中を薄い線で区切る（連絡帳と同じ作り）。
 * 行は、種類のアイコン・文字・時刻、押せる行は右に矢印。未読は、薄い青の背景・太字・「new」の印の 3 つで示す。
 */
export function Notifications() {
  const notifications = useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: () => api.get<FamilyNotification[]>('/api/family/notifications'),
  })

  if (notifications.isPending) return <Message k="layout.loading" />
  if (notifications.isError) return <Message k={messageKeyOf(notifications.error)} />
  return <NotificationsView notifications={notifications.data} />
}

/** 画面の中身（テストではこれを直接出す）。 */
export function NotificationsView({
  notifications,
  now,
}: {
  notifications: FamilyNotification[]
  // テスト用（今日・昨日の判定）
  now?: Date
}) {
  const unread = unreadCount(notifications)
  return (
    <section className="space-y-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">
          <Text k="notifications.title" />
        </h1>
        {unread > 0 && <UnreadCount count={unread} />}
      </div>
      {notifications.length === 0 ? (
        // 出すのは、一覧が 0 件のときだけ（読んだお知らせも一覧に残るので、「新しい…はありません」とは書かない。13.4）
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          {/* キャラクターは飾り（読み上げない）。ホームと同じく、4.8 秒だけふわふわ動いて止まる
              （動きを減らす設定では動かない。index.css の mascot-float。デザインの決めごと 12.4） */}
          <img
            src={mascotFace}
            alt=""
            width={308}
            height={263}
            className="mascot-float h-auto w-28 drop-shadow-md"
          />
          <p className="text-lg font-bold">
            <Text k="notifications.empty" />
          </p>
          <p className="text-ink-sub">
            <Text k="notifications.empty_sub" />
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {groupByDay(notifications, now).map((group) => (
            <DaySection key={group.date} group={group} />
          ))}
        </div>
      )}
    </section>
  )
}

/** 上の「未読 ◯ 件」の印。 */
function UnreadCount({ count }: { count: number }) {
  const { t } = useTranslation()
  return (
    <span className="rounded-full bg-primary-soft px-3 py-1 text-sm font-bold text-primary-dark">
      <Ruby text={t('notifications.unread_count', { count })} />
    </span>
  )
}

/** 1 日分：見出しと、1 つの白い面（中は薄い線で区切る）。 */
function DaySection({ group }: { group: DayGroup }) {
  const { t, i18n } = useTranslation()
  const [, month, day] = group.date.split('-').map(Number)
  const heading = t(`notifications.day_${group.kind}`, {
    month,
    day,
    weekday: weekdayOf(group.date, i18n.language),
  })
  return (
    <section className="space-y-2">
      <h2 className="ml-1 text-sm font-bold text-ink-sub">
        <Ruby text={heading} />
      </h2>
      <ul className="overflow-hidden rounded-2xl border border-card-line bg-card">
        {group.items.map((notification) => (
          <li key={notification.id} className="border-t border-card-line first:border-t-0">
            <NoticeRow notification={notification} />
            {notification.memo_dates.length > 0 && (
              <MemoDateLinks dates={notification.memo_dates} unread={!notification.read} />
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** 1 行：種類のアイコン・文字・時刻。押せる行は、右に矢印。 */
function NoticeRow({ notification }: { notification: FamilyNotification }) {
  const to = linkFor(notification)
  const unread = !notification.read
  const body = (
    <>
      <span
        aria-hidden="true"
        className={`flex size-10 shrink-0 items-center justify-center rounded-full ${
          unread ? 'bg-primary-soft text-primary' : 'bg-page text-ink-sub'
        }`}
      >
        <Icon name={noticeIconName(notification.kind)} className="text-lg" />
      </span>
      <span className="min-w-0 flex-1">
        <span className={`block ${unread ? 'font-bold' : ''}`}>
          <Text k={noticeKey(notification)} />
        </span>
        <span className="mt-0.5 flex items-center gap-2 text-sm text-ink-sub">
          {/* 「new」は小文字で、突き出る部分がなく、枠の中で下に寄って見える。下に 3px 足して、縦中央に見せる（PR #400 ようこさん） */}
          {unread && (
            <span className="rounded bg-primary px-1.5 pb-[3px] text-xs font-bold text-white">
              <Text k="notifications.unread" />
            </span>
          )}
          {timeOf(notification.created_at)}
        </span>
      </span>
      {to && <Icon name="next" className="shrink-0 text-ink-sub" />}
    </>
  )
  const className = `flex min-h-16 items-center gap-3 py-3 pl-3 pr-4 ${unread ? 'bg-unread' : ''}`
  return to ? (
    <Link to={to} className={`${className} hover:bg-primary-soft`}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  )
}

/**
 * まとめに入った様子のメモの、書いた日。押すと、その日の連絡帳へ（メモ自体は、書いた日の連絡帳に出る。
 * spec 007 の FR-012b）。中身は出さない。行のリンクの外に置く（リンクの中にリンクを置かない）。
 */
function MemoDateLinks({ dates, unread }: { dates: string[]; unread: boolean }) {
  const { t } = useTranslation()
  return (
    <div
      className={`flex flex-wrap items-center gap-2 pb-3 pl-16 pr-4 text-sm ${unread ? 'bg-unread' : ''}`}
    >
      <span className="text-ink-sub">
        <Text k="notifications.memo_label" />
      </span>
      {dates.map((date) => {
        const [, month, day] = date.split('-').map(Number)
        return (
          <Link
            key={date}
            to={memoDateLink(date)}
            className="inline-flex min-h-11 items-center gap-1 rounded-full bg-primary-soft px-4 font-bold text-primary-dark hover:bg-primary hover:text-white"
          >
            <Ruby text={t('notifications.memo_date_link', { month, day })} />
            <Icon name="next" className="text-xs" />
          </Link>
        )
      })}
    </div>
  )
}

/** 日本時間の時刻（"20:00"）。日付は、上の見出しにある。 */
function timeOf(iso: string): string {
  return sentAtParts(iso).time
}
