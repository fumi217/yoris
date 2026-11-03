import { Outlet } from 'react-router'
import { useMe } from '../../auth/me'
import { StaffHeader } from '../../components/StaffHeader'
import { usePageTitle } from '../../components/usePageTitle'
import { staffTabs } from './staffTabs'
import { useWaitingMemoCount } from './useWaitingMemoCount'
import { useWaitingMessageCount } from './useWaitingMessageCount'

/** 職員の画面の枠。生活相談員・施設長には、管理画面へのリンクも出す。下の段に、行き先のタブ（#437）。 */
export function StaffLayout() {
  // ブラウザのタブの題：「職員の画面 ｜ YORIS」（画面ごとの題は、10 章の 2.4.2 で別に付ける。#330）
  usePageTitle('layout.to_staff')
  const role = useMe().data?.role ?? null
  const messages = useWaitingMessageCount()
  const approvals = useWaitingMemoCount(role === 'leader' || role === 'director')
  return (
    <div className="mx-auto min-h-screen max-w-3xl">
      <StaffHeader
        homeTo="/staff"
        titleKey="layout.to_staff"
        otherArea="admin"
        otherTo="/admin"
        otherKey="layout.to_admin"
        tabs={staffTabs(role, { messages, approvals })}
        tabsLabelKey="layout.to_staff"
      />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
