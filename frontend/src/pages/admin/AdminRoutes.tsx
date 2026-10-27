import { Navigate, Route, Routes } from 'react-router'
import { AreaGuard } from '../../components/AreaGuard'
import { FamilyMessage } from '../staff/FamilyMessage'
import { FamilyMessages } from '../staff/FamilyMessages'
import { AdminHome } from './AdminHome'
import { AdminLayout } from './AdminLayout'
import { Billing } from './Billing'
import { DisclosureSettings } from './DisclosureSettings'
import { VisitSettings } from './VisitSettings'

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
          {/* 家族からのメッセージ（UI-S08・UI-S09。004-T029 みさき。職員の画面と同じ画面。事務員の入り口） */}
          <Route path="messages" element={<FamilyMessages />} />
          <Route path="messages/:messageId" element={<FamilyMessage />} />
          {/* 利用料のお支払い（spec 002 の T026。施設長・事務員） */}
          <Route path="billing" element={<Billing />} />
          {/* 面会の設定（UI-A02。003-T025 ゆう。事務員・生活相談員・施設長） */}
          <Route path="visit-settings" element={<VisitSettings />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Route>
      </Routes>
    </AreaGuard>
  )
}
