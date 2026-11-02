import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Icon } from '../../components/Icon'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { LogoutButton } from '../../components/LogoutButton'
import { Text } from '../../components/Text'
import { familyMoreMenu, type FamilyMenuItem } from './menu'

// 「その他」の 2 つのまとまり（#401）。メニューの項目は menu.ts、ここは、どれをどこに置くかだけ決める
const TALK_PATHS = ['/family/notifications', '/family/inquiry']
const talkItems = familyMoreMenu.filter((item) => TALK_PATHS.includes(item.to))
const appItems = familyMoreMenu.filter((item) => !TALK_PATHS.includes(item.to))

/**
 * 「その他」の中身（#401）。見出し・「施設とのやりとり」（お知らせ・お問い合わせ）・
 * 「アプリの設定」（設定・表示する言葉）・ログアウト。お知らせと同じ作り（1 つの白い面に行を並べ、薄い線で区切る）。
 */
export function FamilyMorePage() {
  return (
    <section className="space-y-5 p-4">
      <h1 className="text-2xl font-bold">
        <Text k="layout.family_menu.more" />
      </h1>

      <Group titleKey="layout.family_menu_group.talk">
        {talkItems.map((item) => (
          <MoreRow key={item.to} item={item} />
        ))}
      </Group>

      <Group titleKey="layout.family_menu_group.app">
        {appItems.map((item) => (
          <MoreRow key={item.to} item={item} />
        ))}
        <li className="space-y-1 border-t border-card-line p-3">
          <label htmlFor="family-language" className="flex items-center gap-3 font-bold">
            <RowIcon name="language" />
            <Text k="layout.language_label" />
          </label>
          <LanguageSwitcher
            id="family-language"
            className="min-h-11 w-full rounded-xl border border-field-line bg-white px-3"
          />
        </li>
      </Group>

      <LogoutButton
        icon={<Icon name="logout" />}
        className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-field-line bg-white font-bold text-ink shadow-sm"
      />
    </section>
  )
}

/** 見出しと、1 つの白い面（中は薄い線で区切る）。 */
function Group({ titleKey, children }: { titleKey: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="ml-1 text-sm font-bold text-ink-sub">
        <Text k={titleKey} />
      </h2>
      <ul className="overflow-hidden rounded-2xl border border-card-line bg-card">{children}</ul>
    </section>
  )
}

function RowIcon({ name }: { name: 'language' | FamilyMenuItem['icon'] }) {
  return (
    <span
      aria-hidden="true"
      className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary"
    >
      <Icon name={name} className="text-lg" />
    </span>
  )
}

/** 1 行：アイコン・名前・一言の説明・右の矢印。 */
function MoreRow({ item }: { item: FamilyMenuItem }) {
  return (
    <li className="border-t border-card-line first:border-t-0">
      <Link
        to={item.to}
        className="flex min-h-16 items-center gap-3 py-3 pl-3 pr-4 hover:bg-primary-soft"
      >
        <RowIcon name={item.icon} />
        <span className="min-w-0 flex-1">
          <span className="block font-bold">
            <Text k={item.labelKey} />
          </span>
          {item.descKey && (
            <span className="block text-sm text-ink-sub">
              <Text k={item.descKey} />
            </span>
          )}
        </span>
        <Icon name="next" className="shrink-0 text-ink-sub" />
      </Link>
    </li>
  )
}
