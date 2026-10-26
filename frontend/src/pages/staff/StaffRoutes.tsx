import { Navigate, Route, Routes } from 'react-router'
import { AreaGuard } from '../../components/AreaGuard'
import { ResidentList } from './ResidentList'
import { StaffLayout } from './StaffLayout'

/** 職員の画面（/staff 以下。事務員は開けない）。担当は、自分の画面の ComingSoon を差し替える。 */
export default function StaffRoutes() {
  return (
    <AreaGuard area="staff">
      <Routes>
        <Route element={<StaffLayout />}>
          {/* 入居者一覧（UI-S01。001-T031 ゆう） */}
          <Route index element={<ResidentList />} />
          <Route path="*" element={<Navigate to="/staff" replace />} />
        </Route>
      </Routes>
    </AreaGuard>
  )
}
