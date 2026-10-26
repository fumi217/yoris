import { Link } from 'react-router'
import { canOpen, useMe, type Area } from '../auth/me'
import { Text } from './Text'

type Props = {
  // 左の題（押すと、そのまとまりのトップへ）
  homeTo: string
  titleKey: string
  // もう一方のまとまり（職員の画面 ⇔ 管理画面）。開ける人にだけリンクを出す
  otherArea: Area
  otherTo: string
  otherKey: string
}

/** 職員の画面・管理画面の上の部分。 */
export function StaffHeader({ homeTo, titleKey, otherArea, otherTo, otherKey }: Props) {
  const me = useMe().data

  return (
    <header className="flex items-center justify-between border-b p-4">
      <Link to={homeTo} className="text-lg font-bold">
        <Text k={titleKey} />
      </Link>
      <div className="flex items-center gap-4 text-sm">
        {me && canOpen(me, otherArea) && (
          <Link to={otherTo} className="text-sky-700 underline">
            <Text k={otherKey} />
          </Link>
        )}
        <span>{me?.display_name}</span>
      </div>
    </header>
  )
}
