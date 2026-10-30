import '@fortawesome/fontawesome-svg-core/styles.css'
import { config } from '@fortawesome/fontawesome-svg-core'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBars,
  faBell,
  faBookOpen,
  faCalendarDays,
  faCircleQuestion,
  faComments,
  faGear,
  faImages,
  type IconDefinition,
} from '@fortawesome/free-solid-svg-icons'

// CSS は styles.css で読み込む（実行時に style を足さない）。技術選定「アイコン」のとおり
config.autoAddCss = false

/**
 * 用途の名前 → Font Awesome のアイコン。**同じ用途には同じアイコンを使う**（画面ごとに変えない）。
 * アイコンを足すときは、ここに 1 行と、デザインの決めごとの 14 章の対応表に 1 行。
 * 「目」のアイコン（監視されているように見える）は使わない（決めごと 14 章）。
 * Free（solid）のアイコンだけを使う。Pro は使わない。
 */
const ICONS = {
  // 家族の下のメニューと、「その他」の中（menu.ts）
  'contact-book': faBookOpen,
  requests: faCircleQuestion,
  inquiry: faComments,
  notifications: faBell,
  more: faBars,
  visits: faCalendarDays,
  album: faImages,
  settings: faGear,
} as const satisfies Record<string, IconDefinition>

export type IconName = keyof typeof ICONS

type Props = {
  name: IconName
  // アイコンだけで意味を伝えるときの名前（読み上げ。1.1.1・4.1.2）。ふつうは、横に文字があるので付けない（飾りとして読み上げない）
  label?: string
  className?: string
}

/**
 * アイコン。Font Awesome は、ここだけで呼ぶ。色は文字と同じ（`currentColor`）、大きさは文字と同じ
 * （`font-size`。`text-lg` などで変える）、横幅は固定（並べたときにそろう）。
 * Font Awesome は、`role="img"` を自動で付ける。飾りのときは `aria-hidden` で読み上げから外れる。
 */
export function Icon({ name, label, className }: Props) {
  return (
    <FontAwesomeIcon
      icon={ICONS[name]}
      fixedWidth
      className={className}
      aria-hidden={label ? undefined : true}
      aria-label={label}
    />
  )
}
