import { Outlet } from 'react-router'
import { StaffHeader } from '../../components/StaffHeader'

/** 職員の画面の枠。生活相談員・施設長には、管理画面へのリンクも出す。 */
export function StaffLayout() {
  return (
    <div className="mx-auto min-h-screen max-w-3xl">
      <StaffHeader
        homeTo="/staff"
        titleKey="layout.app_name"
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
