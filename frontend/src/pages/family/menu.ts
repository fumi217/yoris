// 家族の画面のメニュー（spec 001 の Clarifications・T019）。
// 下に連絡帳・知りたいこと・面会予約・アルバム、そのほか（お知らせ・お問い合わせ・設定）は「その他」（≡）にまとめる（spec 001 の Session 2026-10-30。#396。PR #397 のレビューで、「知りたいこと」を下に残す案 A にした）。項目を足すときは、ここに 1 行と、FamilyRoutes.tsx に画面を 1 行足す。

import type { IconName } from '../../components/Icon'
import type { FamilyFeatures } from './albumView'

export type FamilyMenuItem = {
  to: string
  labelKey: string
  // 用途の名前（components/Icon.tsx）。同じ用途には同じアイコン
  icon: IconName
}

// 画面の下に並べる（「その他」を足して 5 つまで。これ以上増やさない。面会は spec 003 の T014、アルバムは spec 005 が中身を作る）
export const familyMainMenu: FamilyMenuItem[] = [
  { to: '/family', labelKey: 'layout.family_menu.contact_book', icon: 'contact-book' },
  { to: '/family/requests', labelKey: 'layout.family_menu.requests', icon: 'requests' },
  { to: '/family/visits', labelKey: 'layout.family_menu.visits', icon: 'visits' },
  { to: '/family/album', labelKey: 'layout.family_menu.album', icon: 'album' },
]

// 「その他」の中（「お問い合わせ」は spec 004 の T020。連絡帳のキャラクターからも開ける。「お知らせ」は、返事が届くと連絡帳のいちばん上に未読の返事が出る）
export const familyMoreMenu: FamilyMenuItem[] = [
  {
    to: '/family/notifications',
    labelKey: 'layout.family_menu.notifications',
    icon: 'notifications',
  },
  { to: '/family/inquiry', labelKey: 'layout.family_menu.inquiry', icon: 'inquiry' },
  { to: '/family/settings', labelKey: 'layout.family_menu.settings', icon: 'settings' },
]

/**
 * 家族の画面の、ブラウザのタブの題に使う名前（辞書のキー）。下のメニューと「その他」の名前から決める
 * （`/family` は連絡帳、`/family/more` は「その他」。メニューにない画面は null で、アプリの名前だけになる。#330）。
 */
export function familyTitleKey(pathname: string): string | null {
  const path = pathname.replace(/\/+$/, '') || '/'
  if (path === '/family') return 'layout.family_menu.contact_book'
  if (path === '/family/more') return 'layout.family_menu.more'
  // `/family`（連絡帳）は、すべての家族の画面の頭にあたるので、前方一致の対象にしない（上で決めた）
  const item = [...familyMainMenu, ...familyMoreMenu]
    .filter((menuItem) => menuItem.to !== '/family')
    .find((menuItem) => path === menuItem.to || path.startsWith(`${menuItem.to}/`))
  return item?.labelKey ?? null
}

/**
 * 下のメニューに出す項目。アルバムは、開示設定で「見せる」と分かったときだけ出す
 * （`GET /api/family/features` の答えが来るまでは出さない。出たり消えたりしないように。spec 005 の 005-T013）。
 */
export function visibleMainMenu(features: FamilyFeatures | undefined): FamilyMenuItem[] {
  return familyMainMenu.filter((item) => item.to !== '/family/album' || features?.album === true)
}
