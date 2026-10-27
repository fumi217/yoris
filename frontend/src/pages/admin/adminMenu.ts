// 管理画面のトップに並べる画面（docs/画面設計.md「3」）。役割ごとに、開ける画面だけを出す。
// 画面を足すときは、ここに 1 行と、AdminRoutes.tsx に画面を 1 行足す。守りは API の 403（ここは見た目だけ）。

import type { StaffRole } from '../../auth/me'

export type AdminMenuItem = {
  to: string
  labelKey: string
  icon: string
  roles: StaffRole[]
  // 家族からのメッセージの対応待ちの件数を添える入り口（#88）
  showMessageCount?: boolean
}

export const adminMenu: AdminMenuItem[] = [
  // 開示設定（UI-A01。spec 001 の T040。生活相談員・施設長）
  {
    to: '/admin/disclosure',
    labelKey: 'admin.menu.disclosure',
    icon: '👁️',
    roles: ['counselor', 'director'],
  },
  // 家族からのメッセージ（UI-S08。spec 004 の T029。事務員の入り口。職員の画面と同じ画面を開く）
  {
    to: '/admin/messages',
    labelKey: 'admin.menu.family_messages',
    icon: '📩',
    roles: ['counselor', 'clerk', 'director'],
    showMessageCount: true,
  },
  // 利用料のお支払い（spec 002 の T026。施設長・事務員。守りは API の 403）
  {
    to: '/admin/billing',
    labelKey: 'admin.menu.billing',
    icon: '💳',
    roles: ['director', 'clerk'],
  },
  // 面会の設定（UI-A02。spec 003 の T025。事務員・生活相談員・施設長。開始時刻の候補・組数・休みの日）
  {
    to: '/admin/visit-settings',
    labelKey: 'admin.menu.visit_settings',
    icon: '🗓️',
    roles: ['clerk', 'counselor', 'director'],
  },
  // 面会の予約の一覧（UI-S11。spec 003 の T026。職員の画面と同じ画面。介護職員・リーダーは職員の画面から開く）
  {
    to: '/admin/visits',
    labelKey: 'admin.menu.visits',
    icon: '📋',
    roles: ['clerk', 'counselor', 'director'],
  },
]

export function adminMenuFor(role: StaffRole | null): AdminMenuItem[] {
  return role ? adminMenu.filter((item) => item.roles.includes(role)) : []
}

/** 管理画面のトップ（`/admin`）か。トップ以外の画面には「管理画面のトップへ」を出す（#256）。 */
export function isAdminHome(pathname: string): boolean {
  return pathname.replace(/\/+$/, '') === '/admin'
}
