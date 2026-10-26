import { Outlet } from 'react-router'
import { StaffHeader } from '../../components/StaffHeader'

/** 管理画面の枠。職員の画面も開ける人（生活相談員・施設長）には、職員の画面へのリンクを出す。 */
export function AdminLayout() {
  return (
    <div className="mx-auto min-h-screen max-w-3xl">
      <StaffHeader
        homeTo="/admin"
        titleKey="layout.to_admin"
        otherArea="staff"
        otherTo="/staff"
        otherKey="layout.to_staff"
      />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
