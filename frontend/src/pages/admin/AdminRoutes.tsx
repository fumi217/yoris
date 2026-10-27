import { Navigate, Route, Routes } from 'react-router'
import { AreaGuard } from '../../components/AreaGuard'
import { AdminHome } from './AdminHome'
import { AdminLayout } from './AdminLayout'
import { Billing } from './Billing'
import { DisclosureSettings } from './DisclosureSettings'

/**
 * 管理画面（/admin 以下。生活相談員・施設長・事務員）。担当は、自分の画面の Route を足す。
 * 画面ごとに開ける役割が違うときは、API の 403 で守る（画面で隠すのは見た目のため）。
 */
export default function AdminRoutes() {
  return (
    <AreaGuard area="admin">
      <Routes>
        <Route element={<AdminLayout />}>
          {/* 管理画面のトップ（各担当の画面への入り口。並べる画面は adminMenu.ts） */}
          <Route index element={<AdminHome />} />
          {/* 開示設定（UI-A01。001-T040 ゆう） */}
          <Route path="disclosure" element={<DisclosureSettings />} />
          {/* 利用料のお支払い（spec 002 の T026。施設長・事務員） */}
          <Route path="billing" element={<Billing />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Route>
      </Routes>
    </AreaGuard>
  )
}
