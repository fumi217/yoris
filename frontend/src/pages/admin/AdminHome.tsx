import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useMe } from '../../auth/me'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { useWaitingMessageCount } from '../staff/useWaitingMessageCount'
import { adminMenuFor } from './adminMenu'

/** 管理画面のトップ。ログイン中の役割で開ける画面を並べる（adminMenu.ts）。 */
export function AdminHome() {
  const { t } = useTranslation()
  const items = adminMenuFor(useMe().data?.role ?? null)
  const waitingMessages = useWaitingMessageCount()

  if (items.length === 0) return <Message k="admin.no_menu" />
  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={item.to}>
          <Link to={item.to} className="flex items-center gap-3 p-4">
            <span aria-hidden="true">{item.icon}</span>
            {/* ふりがなの部品は漢字ごとに分かれるので、包んで 1 つにする（flex の gap でばらけないように） */}
            <span>
              <Text k={item.labelKey} />
            </span>
            {/* 対応待ちの件数（1 件以上のときだけ。通知・音は出さない。FR-013） */}
            {item.showMessageCount && waitingMessages > 0 && (
              <span className="rounded-full bg-orange-100 px-2 py-0.5 text-sm font-bold text-orange-800">
                <span aria-hidden="true">{waitingMessages}</span>
                {/* 読み上げでは「3」だけにならないよう、何の数かを添える（PR #234 ようこ・ゆう） */}
                <span className="sr-only">
                  <Ruby text={t('admin.waiting_messages', { count: waitingMessages })} />
                </span>
              </span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  )
}
