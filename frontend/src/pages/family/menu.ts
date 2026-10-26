// 家族の画面のメニュー（spec 001 の Clarifications・T019）。
// 下に 4 つ、そのほかは「☰ その他」にまとめる。項目を足すときは、ここに 1 行と、FamilyRoutes.tsx に画面を 1 行足す。

export type FamilyMenuItem = {
  to: string
  labelKey: string
  icon: string
}

// 画面の下に並べる 4 つ（これ以上増やさない。「お問い合わせ」は spec 001 の Session 2026-10-26・spec 004 の T020）
export const familyMainMenu: FamilyMenuItem[] = [
  { to: '/family', labelKey: 'layout.family_menu.contact_book', icon: '📖' },
  { to: '/family/requests', labelKey: 'layout.family_menu.requests', icon: '💬' },
  { to: '/family/inquiry', labelKey: 'layout.family_menu.inquiry', icon: '🤖' },
  { to: '/family/notifications', labelKey: 'layout.family_menu.notifications', icon: '🔔' },
]

// 「☰ その他」の中（面会は spec 003 の T014、アルバムは spec 005 が中身を作る）
export const familyMoreMenu: FamilyMenuItem[] = [
  { to: '/family/visits', labelKey: 'layout.family_menu.visits', icon: '📅' },
  { to: '/family/album', labelKey: 'layout.family_menu.album', icon: '🖼️' },
  { to: '/family/settings', labelKey: 'layout.family_menu.settings', icon: '⚙️' },
]
