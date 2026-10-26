import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
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
        <p className="text-gray-600">
          <Text k="notifications.empty" />
        </p>
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
