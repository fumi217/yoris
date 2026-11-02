import '@fortawesome/fontawesome-svg-core/styles.css'
import { config } from '@fortawesome/fontawesome-svg-core'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBagShopping,
  faBars,
  faBed,
  faBell,
  faBookOpen,
  faBullhorn,
  faCalendarCheck,
  faCalendarDays,
  faCalendarWeek,
  faChevronDown,
  faCalendarXmark,
  faCamera,
  faCheck,
  faChevronLeft,
  faChevronRight,
  faCircleCheck,
  faCircleInfo,
  faCircleQuestion,
  faClipboardList,
  faClock,
  faCloudSun,
  faCommentDots,
  faComments,
  faCookieBite,
  faCreditCard,
  faEnvelope,
  faFaceSmile,
  faFile,
  faGear,
  faGlobe,
  faHandshake,
  faHeart,
  faHouse,
  faImages,
  faLockOpen,
  faMoon,
  faPalette,
  faPaperPlane,
  faPenToSquare,
  faPhone,
  faPhoneVolume,
  faRightFromBracket,
  faSquareCheck,
  faSun,
  faTriangleExclamation,
  faUpload,
  faUserTie,
  faUsers,
  faUtensils,
  faXmark,
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
  language: faGlobe,
  logout: faRightFromBracket,
  // 連絡帳（#382）
  prev: faChevronLeft,
  expand: faChevronDown,
  close: faXmark,
  next: faChevronRight,
  date: faCalendarDays,
  weekly: faCalendarWeek,
  meal: faUtensils,
  mood: faFaceSmile,
  sleep: faBed,
  breakfast: faCloudSun,
  lunch: faSun,
  dinner: faMoon,
  snack: faCookieBite,
  phone: faPhone,
  'empty-record': faClipboardList,
  // お知らせの種類（#399）
  'notice-reply': faCommentDots,
  'notice-visit-confirmed': faCalendarCheck,
  'notice-visit-cancelled': faCalendarXmark,
  'notice-announcement': faBullhorn,
  // 知りたいこと（#385）
  send: faPaperPlane,
  'selected-count': faSquareCheck,
  checked: faCircleCheck,
  'theme-daily-life': faHouse,
  'theme-enjoying': faFaceSmile,
  'theme-residents': faUsers,
  // 職員の画面の「返事待ち」（家族の画面では使わない）
  'request-waiting': faCommentDots,
  'theme-meals': faUtensils,
  'theme-staff': faHandshake,
  'theme-recreation': faPalette,
  'theme-family-talk': faHeart,
  'theme-supplies': faBagShopping,
  // 残りの絵文字の置き換え（#388）
  check: faCheck,
  warning: faTriangleExclamation,
  info: faCircleInfo,
  camera: faCamera,
  memo: faPenToSquare,
  'family-message': faEnvelope,
  billing: faCreditCard,
  'visit-settings': faCalendarCheck,
  'visit-list': faClipboardList,
  'staff-account': faUserTie,
  disclosure: faLockOpen,
  'upload-waiting': faClock,
  uploading: faUpload,
  file: faFile,
  'urgent-call': faPhoneVolume,
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
