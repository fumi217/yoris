import { Link } from 'react-router'
import { Icon } from '../../components/Icon'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { LogoutButton } from '../../components/LogoutButton'
import { Text } from '../../components/Text'
import { familyMoreMenu } from './menu'

/** 「その他」の中身。menu.ts の項目（知りたいこと・お問い合わせ・設定）を並べ、最後に言語とログアウト。 */
export function FamilyMorePage() {
  return (
    <ul className="divide-y">
      {familyMoreMenu.map((item) => (
        <li key={item.to}>
          <Link to={item.to} className="flex items-center gap-3 p-4">
            <Icon name={item.icon} className="text-lg text-primary" />
            <Text k={item.labelKey} />
          </Link>
        </li>
      ))}
      <li className="flex flex-wrap items-center gap-3 p-4">
        <LanguageSwitcher className="rounded border border-field-line p-1" />
        <LogoutButton className="text-primary underline" />
      </li>
    </ul>
  )
}
