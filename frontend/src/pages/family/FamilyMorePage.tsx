import { Link } from 'react-router'
import { LogoutButton } from '../../components/LogoutButton'
import { Text } from '../../components/Text'
import { familyMoreMenu } from './menu'

/** 「☰ その他」の中身。menu.ts の familyMoreMenu を並べ、最後にログアウト。 */
export function FamilyMorePage() {
  return (
    <ul className="divide-y">
      {familyMoreMenu.map((item) => (
        <li key={item.to}>
          <Link to={item.to} className="flex items-center gap-3 p-4">
            <span aria-hidden="true">{item.icon}</span>
            <Text k={item.labelKey} />
          </Link>
        </li>
      ))}
      <li className="flex flex-wrap items-center gap-3 p-4">
        <LogoutButton className="text-sky-700 underline" />
      </li>
    </ul>
  )
}
