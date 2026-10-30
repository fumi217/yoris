import { Link, Outlet, useLocation } from 'react-router'
import { Icon } from '../../components/Icon'
import { StaffHeader } from '../../components/StaffHeader'
import { Text } from '../../components/Text'
import { usePageTitle } from '../../components/usePageTitle'
import { isAdminHome } from './adminMenu'

/** 管理画面の枠。職員の画面も開ける人（生活相談員・施設長）には、職員の画面へのリンクを出す。 */
export function AdminLayout() {
  const { pathname } = useLocation()
  // ブラウザのタブの題：「管理画面 ｜ YORIS」（画面ごとの題は、10 章の 2.4.2 で別に付ける。#330）
  usePageTitle('layout.to_admin')
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
        <BackToAdmin pathname={pathname} />
        <Outlet />
      </main>
    </div>
  )
}

/**
 * トップ以外の管理画面のいちばん上に出す「◀ 管理画面のトップへ」（#256）。
 * 上の「管理画面」の文字でも戻れるが、題にしか見えず気づきにくいため。
 * 枠に置くので、管理画面を足しても、画面ごとに足さなくてよい。
 */
export function BackToAdmin({ pathname }: { pathname: string }) {
  if (isAdminHome(pathname)) return null
  return (
    <nav className="px-4 pt-3 text-sm">
      <Link to="/admin" className="text-primary underline">
        <Icon name="prev" className="mr-1" />
        <Text k="layout.back_to_admin" />
      </Link>
    </nav>
  )
}
