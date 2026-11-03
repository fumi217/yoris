// 管理画面のトップに並べる画面（docs/画面設計.md「3」）。役割ごとに、開ける画面だけを出す。
// 画面を足すときは、ここに 1 行と、AdminRoutes.tsx に画面を 1 行足す。守りは API の 403（ここは見た目だけ）。

import type { StaffRole } from '../../auth/me'
import type { TabItem } from '../../components/AreaTabs'
import type { IconName } from '../../components/Icon'

export type AdminMenuItem = {
  to: string
  labelKey: string
  // タブの短い名前（上の枠のタブ。狭い幅でも 4 つずつ並ぶように。#437）
  tabLabelKey: string
  icon: IconName
  roles: StaffRole[]
  // 家族からのメッセージの対応待ちの件数を添える入り口（#88）
  showMessageCount?: boolean
}

export const adminMenu: AdminMenuItem[] = [
  // 開示設定（UI-A01。spec 001 の T040。生活相談員・施設長）
  {
    to: '/admin/disclosure',
    labelKey: 'admin.menu.disclosure',
    tabLabelKey: 'layout.admin_tab.disclosure',
    icon: 'disclosure',
    roles: ['counselor', 'director'],
  },
  // 変化の目印の設定（spec 006 の T021。生活相談員・施設長。守りは API の 403）
  {
    to: '/admin/change-rules',
    labelKey: 'admin.menu.change_rules',
    tabLabelKey: 'layout.admin_tab.change_rules',
    icon: 'warning',
    roles: ['counselor', 'director'],
  },
  // 家族からのメッセージ（UI-S08。spec 004 の T029。事務員の入り口。職員の画面と同じ画面を開く）
  {
    to: '/admin/messages',
    labelKey: 'admin.menu.family_messages',
    tabLabelKey: 'layout.admin_tab.messages',
    icon: 'family-message',
    roles: ['counselor', 'clerk', 'director'],
    showMessageCount: true,
  },
  // 利用料のお支払い（spec 002 の T026。施設長・事務員。守りは API の 403）
  {
    to: '/admin/billing',
    labelKey: 'admin.menu.billing',
    tabLabelKey: 'layout.admin_tab.billing',
    icon: 'billing',
    roles: ['director', 'clerk'],
  },
  // 面会の設定（UI-A02。spec 003 の T025。事務員・生活相談員・施設長。開始時刻の候補・組数・休みの日）
  {
    to: '/admin/visit-settings',
    labelKey: 'admin.menu.visit_settings',
    tabLabelKey: 'layout.admin_tab.visit_settings',
    icon: 'visit-settings',
    roles: ['clerk', 'counselor', 'director'],
  },
  // 面会の予約の一覧（UI-S11。spec 003 の T026。職員の画面と同じ画面。介護職員・リーダーは職員の画面から開く）
  {
    to: '/admin/visits',
    labelKey: 'admin.menu.visits',
    tabLabelKey: 'layout.admin_tab.visits',
    icon: 'visit-list',
    roles: ['clerk', 'counselor', 'director'],
  },
  // 職員のアカウントを作る（001-T088。生活相談員・施設長。守りは API の 403）
  {
    to: '/admin/staff-accounts',
    labelKey: 'admin.menu.staff_accounts',
    tabLabelKey: 'layout.admin_tab.staff_accounts',
    icon: 'staff-account',
    roles: ['counselor', 'director'],
  },
]

export function adminMenuFor(role: StaffRole | null): AdminMenuItem[] {
  return role ? adminMenu.filter((item) => item.roles.includes(role)) : []
}

/** 管理画面のトップ（`/admin`）か。トップ以外の画面には「管理画面のトップへ」を出す（#256）。 */
export function isAdminHome(pathname: string): boolean {
  return pathname.replace(/\/+$/, '') === '/admin'
}

/**
 * 管理画面のタブ（デザインの決めごと 8 章。#437）：トップと、その人の役割で開ける画面。
 * メッセージには、対応待ちの件数を添える。詳細の画面でも、もとのタブを選ばれた状態にする。
 */
export function adminTabs(role: StaffRole | null, messageCount: number): TabItem[] {
  return [
    {
      to: '/admin',
      labelKey: 'layout.admin_tab.home',
      icon: 'home',
      isActive: isAdminHome,
    },
    ...adminMenuFor(role).map((item) => ({
      to: item.to,
      labelKey: item.tabLabelKey,
      icon: item.icon,
      count: item.showMessageCount ? messageCount : undefined,
      isActive: (pathname: string) => pathname.startsWith(item.to),
    })),
  ]
}
