import { Navigate, Route, Routes } from 'react-router'
import { AreaGuard } from '../../components/AreaGuard'
import { ComingSoon } from '../../components/ComingSoon'
import { AdminLayout } from './AdminLayout'

/**
 * 管理画面（/admin 以下。生活相談員・施設長・事務員）。担当は、自分の画面の Route を足す。
 * 画面ごとに開ける役割が違うときは、API の 403 で守る（画面で隠すのは見た目のため）。
 */
export default function AdminRoutes() {
  return (
    <AreaGuard area="admin">
      <Routes>
        <Route element={<AdminLayout />}>
          {/* 管理画面のトップ（開示設定 UI-A01 001-T040 など、各担当の画面への入り口） */}
          <Route index element={<ComingSoon />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Route>
      </Routes>
    </AreaGuard>
  )
}
