import { Navigate, Route, Routes } from 'react-router'
import { AreaGuard } from '../../components/AreaGuard'
import { AlbumUpload } from './AlbumUpload'
import { FamilyMessage } from './FamilyMessage'
import { FamilyMessages } from './FamilyMessages'
import { MemoApprovals } from './MemoApprovals'
import { MemoEditor } from './MemoEditor'
import { RecordPage } from './RecordPage'
import { ReplyPage } from './ReplyPage'
import { ResidentList } from './ResidentList'
import { StaffContactBook } from './StaffContactBook'
import { StaffLayout } from './StaffLayout'
import { TodayVisits } from './TodayVisits'
import { VisitReservations } from './VisitReservations'

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
          {/* 写真を載せる（UI-S10。005-T014 さとこ。記録の画面の「📷 写真を載せる」から） */}
          <Route path="residents/:residentId/album" element={<AlbumUpload />} />
          {/* 様子のメモを書く（UI-S05。007-T011 みさき。介護職員・リーダー。守りは API の 403） */}
          <Route path="residents/:residentId/memos/new" element={<MemoEditor />} />
          {/* 様子のメモの承認（UI-S07。007-T023 みさき。リーダー・施設長。守りは API の 403） */}
          <Route path="memo-approvals" element={<MemoApprovals />} />
          {/* 連絡帳の見返し（UI-S04。001-T033 ゆう） */}
          <Route path="residents/:residentId/contact-book" element={<StaffContactBook />} />
          {/* 職員の返事（UI-S03。001-T062 ゆう） */}
          <Route path="residents/:residentId/requests" element={<ReplyPage />} />
          {/* 家族からのメッセージ（UI-S08・UI-S09。004-T029 みさき。管理画面からも同じ画面を開く） */}
          <Route path="messages" element={<FamilyMessages />} />
          <Route path="messages/:messageId" element={<FamilyMessage />} />
          {/* 面会の予約の一覧（UI-S11）と今日の面会予定（UI-S12）。003-T026・T027 ゆう */}
          <Route path="visits" element={<VisitReservations />} />
          <Route path="visits/today" element={<TodayVisits />} />
          <Route path="*" element={<Navigate to="/staff" replace />} />
        </Route>
      </Routes>
    </AreaGuard>
  )
}
