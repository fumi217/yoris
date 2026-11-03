import type { TabItem } from '../../components/AreaTabs'
import type { StaffRole } from '../../auth/me'

/**
 * 職員の画面のタブ（デザインの決めごと 8 章。#437）。
 * 家族からのメッセージ・面会予定は、職員の 4 つの役割すべて。様子のメモの承認は、リーダー・施設長だけ
 * （見た目だけ。守りは API の 403）。件数は、ある人にだけ添える。
 * 入居者の詳細（記録・返事・連絡帳・メモ）の画面でも、「入居者一覧」のタブを選ばれた状態にする。
 */
export function staffTabs(
  role: StaffRole | null,
  counts: { messages: number; approvals: number },
): TabItem[] {
  const items: TabItem[] = [
    {
      to: '/staff',
      labelKey: 'layout.staff_tab.residents',
      icon: 'residents',
      isActive: (path) => path === '/staff' || path.startsWith('/staff/residents'),
    },
    {
      to: '/staff/messages',
      labelKey: 'layout.staff_tab.messages',
      icon: 'family-message',
      count: counts.messages,
      isActive: (path) => path.startsWith('/staff/messages'),
    },
    {
      to: '/staff/visits/today',
      labelKey: 'layout.staff_tab.visits',
      icon: 'visits',
      isActive: (path) => path.startsWith('/staff/visits'),
    },
  ]
  if (role === 'leader' || role === 'director') {
    items.push({
      to: '/staff/memo-approvals',
      labelKey: 'layout.staff_tab.memo_approvals',
      icon: 'memo',
      count: counts.approvals,
      isActive: (path) => path.startsWith('/staff/memo-approvals'),
    })
  }
  return items
}
