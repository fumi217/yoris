import { Outlet } from 'react-router'
import { useMe } from '../../auth/me'
import { StaffHeader } from '../../components/StaffHeader'
import { usePageTitle } from '../../components/usePageTitle'
import { useWaitingMessageCount } from '../staff/useWaitingMessageCount'
import { adminTabs } from './adminMenu'

/**
 * 管理画面の枠。職員の画面も開ける人（生活相談員・施設長）には、職員の画面へのリンクも出す。
 * 下の段に、行き先のタブ（トップと、その人の役割で開ける画面。#437）。トップ以外から戻る「◀ 管理画面のトップへ」
 * （#256）は、タブの「トップ」で足りるので、出さない。
 */
export function AdminLayout() {
  // ブラウザのタブの題：「管理画面 ｜ YORIS」（画面ごとの題は、10 章の 2.4.2 で別に付ける。#330）
  usePageTitle('layout.to_admin')
  const role = useMe().data?.role ?? null
  const messageCount = useWaitingMessageCount()
  return (
    <div className="mx-auto min-h-screen max-w-3xl">
      <StaffHeader
        homeTo="/admin"
        titleKey="layout.to_admin"
        otherArea="staff"
        otherTo="/staff"
        otherKey="layout.to_staff"
        tabs={adminTabs(role, messageCount)}
        tabsLabelKey="layout.to_admin"
      />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
