import { Link } from 'react-router'
import { canOpen, useMe, type Area } from '../auth/me'
import { LanguageSwitcher } from './LanguageSwitcher'
import { Logo } from './Logo'
import { LogoutButton } from './LogoutButton'
import { Text } from './Text'

type Props = {
  // 左のロゴと題（1 つのリンク。押すと、そのまとまりのトップへ。同じ行き先のリンクを 2 つに分けない。2.4.4）
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
    // 狭い幅（320px）では右側が次の行に折り返す。左のリンクは縮めない（重なり・横あふれを防ぐ。2.4.11・1.4.10）
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b p-4">
      <Link to={homeTo} className="flex shrink-0 items-center gap-3 text-lg font-bold">
        <Logo className="h-8" />
        <Text k={titleKey} />
      </Link>
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {me && canOpen(me, otherArea) && (
          <Link to={otherTo} className="text-primary underline">
            <Text k={otherKey} />
          </Link>
        )}
        <span>{me?.display_name}</span>
        <LanguageSwitcher className="rounded border border-field-line px-1" />
        <LogoutButton className="text-primary underline" />
      </div>
    </header>
  )
}
