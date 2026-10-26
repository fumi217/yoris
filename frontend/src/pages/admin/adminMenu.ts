// 管理画面のトップに並べる画面（docs/画面設計.md「3」）。役割ごとに、開ける画面だけを出す。
// 画面を足すときは、ここに 1 行と、AdminRoutes.tsx に画面を 1 行足す。守りは API の 403（ここは見た目だけ）。

import type { StaffRole } from '../../auth/me'

export type AdminMenuItem = {
  to: string
  labelKey: string
  icon: string
  roles: StaffRole[]
}

export const adminMenu: AdminMenuItem[] = [
  // 開示設定（UI-A01。spec 001 の T040。生活相談員・施設長）
  {
    to: '/admin/disclosure',
    labelKey: 'admin.menu.disclosure',
    icon: '👁️',
    roles: ['counselor', 'director'],
  },
]

export function adminMenuFor(role: StaffRole | null): AdminMenuItem[] {
  return role ? adminMenu.filter((item) => item.roles.includes(role)) : []
}
