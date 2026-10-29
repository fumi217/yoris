import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { api } from '../../api/client'
import { LogoutButton } from '../../components/LogoutButton'
import { Text } from '../../components/Text'
import type { FamilyFeatures } from './albumView'
import { visibleMoreMenu } from './menu'

/** 「☰ その他」の中身。menu.ts の項目（アルバムは「見せる」設定のときだけ）を並べ、最後にログアウト。 */
export function FamilyMorePage() {
  const features = useQuery({
    queryKey: ['family', 'features'],
    queryFn: () => api.get<FamilyFeatures>('/api/family/features'),
  })
  return (
    <ul className="divide-y">
      {visibleMoreMenu(features.data).map((item) => (
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
