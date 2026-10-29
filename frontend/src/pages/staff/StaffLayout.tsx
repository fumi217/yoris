import { Outlet } from 'react-router'
import { StaffHeader } from '../../components/StaffHeader'
import { usePageTitle } from '../../components/usePageTitle'

/** 職員の画面の枠。生活相談員・施設長には、管理画面へのリンクも出す。 */
export function StaffLayout() {
  // ブラウザのタブの題：「職員の画面 ｜ YORIS」（画面ごとの題は、10 章の 2.4.2 で別に付ける。#330）
  usePageTitle('layout.to_staff')
  return (
    <div className="mx-auto min-h-screen max-w-3xl">
      <StaffHeader
        homeTo="/staff"
        titleKey="layout.to_staff"
        otherArea="admin"
        otherTo="/admin"
        otherKey="layout.to_admin"
      />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
