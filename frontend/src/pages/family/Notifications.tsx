import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import mascotFace from '../../assets/brand/mascot-normal.png'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { kindKey, linkFor, type FamilyNotification } from './notificationsView'
import { sentAtParts } from './requestsView'

const NOTIFICATIONS_KEY = ['family', 'notifications'] as const

/**
 * 家族のお知らせの一覧（UI-F04。spec 001 の T061）。`/family/notifications`
 * 届いたお知らせ（返事・まとめ・施設からのお知らせ）を新しい順に出す。まだ読んでいないものは印をつける。
 * 一覧に返事の中身は出さない（API が返さない。中身は連絡帳で見る。SC-010）。
 * 返事のお知らせは、連絡帳で返事を読んだときに既読になる（001-T056）。
 * 1 つもないときは、キャラクターとやわらかい一言を出す（デザインの決めごと 13 章。#350）。
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
export function NotificationsView({ notifications }: { notifications: FamilyNotification[] }) {
  const { t } = useTranslation()
  return (
    <section className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        <Text k="notifications.title" />
      </h1>
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
          <p className="text-gray-600">
            <Text k="notifications.empty_sub" />
          </p>
        </div>
      ) : (
        <ul className="divide-y border-y">
          {notifications.map((notification) => {
            const to = linkFor(notification)
            const body = (
              <>
                <span className={`block ${notification.read ? '' : 'font-bold'}`}>
                  {!notification.read && (
                    <span className="mr-2 rounded bg-sky-700 px-2 py-0.5 text-xs font-normal text-white">
                      <Text k="notifications.unread" />
                    </span>
                  )}
                  <Text k={kindKey(notification.kind)} />
                </span>
                <span className="block text-sm text-gray-600">
                  <Ruby text={t('notifications.at', sentAtParts(notification.created_at))} />
                </span>
              </>
            )
            return (
              <li key={notification.id}>
                {to ? (
                  <Link to={to} className="block py-3">
                    {body}
                  </Link>
                ) : (
                  <div className="py-3">{body}</div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
