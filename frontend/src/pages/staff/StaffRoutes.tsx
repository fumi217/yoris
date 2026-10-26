import { Navigate, Route, Routes } from 'react-router'
import { AreaGuard } from '../../components/AreaGuard'
import { RecordPage } from './RecordPage'
import { ReplyPage } from './ReplyPage'
import { ResidentList } from './ResidentList'
import { StaffContactBook } from './StaffContactBook'
import { StaffLayout } from './StaffLayout'

/** 職員の画面（/staff 以下。事務員は開けない）。担当は、自分の画面の ComingSoon を差し替える。 */
export default function StaffRoutes() {
  return (
    <AreaGuard area="staff">
      <Routes>
        <Route element={<StaffLayout />}>
          {/* 入居者一覧（UI-S01。001-T031 ゆう） */}
          <Route index element={<ResidentList />} />
          {/* 記録の画面（UI-S02。001-T032 ゆう） */}
          <Route path="residents/:residentId" element={<RecordPage />} />
          {/* 連絡帳の見返し（UI-S04。001-T033 ゆう） */}
          <Route path="residents/:residentId/contact-book" element={<StaffContactBook />} />
          {/* 職員の返事（UI-S03。001-T062 ゆう） */}
          <Route path="residents/:residentId/requests" element={<ReplyPage />} />
          <Route path="*" element={<Navigate to="/staff" replace />} />
        </Route>
      </Routes>
    </AreaGuard>
  )
}
