import { Link } from 'react-router'
import { useMe } from '../../auth/me'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { adminMenuFor } from './adminMenu'

/** 管理画面のトップ。ログイン中の役割で開ける画面を並べる（adminMenu.ts）。 */
export function AdminHome() {
  const items = adminMenuFor(useMe().data?.role ?? null)

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
          </Link>
        </li>
      ))}
    </ul>
  )
}
