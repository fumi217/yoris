import { Navigate, Route, Routes } from 'react-router'
import { AreaGuard } from '../../components/AreaGuard'
import { ComingSoon } from '../../components/ComingSoon'
import { ContactBook } from './ContactBook'
import { FamilyLayout } from './FamilyLayout'
import { FamilyMorePage } from './FamilyMorePage'
import { Requests } from './Requests'
import { VisitBooking } from './visits/VisitBooking'

/** 家族の画面（/family 以下）。担当は、自分の画面の ComingSoon を差し替える。 */
export default function FamilyRoutes() {
  return (
    <AreaGuard area="family">
      <Routes>
        <Route element={<FamilyLayout />}>
          {/* 連絡帳（ホーム。001-T059 さとこ） */}
          <Route index element={<ContactBook />} />
          {/* 知りたいことを頼む（001-T060 さとこ） */}
          <Route path="requests/*" element={<Requests />} />
          {/* お知らせの一覧（001-T061 さとこ） */}
          <Route path="notifications" element={<ComingSoon />} />
          <Route path="more" element={<FamilyMorePage />} />
          {/* 面会の予約（003-T014 ゆう） */}
          <Route path="visits" element={<VisitBooking />} />
          {/* アルバム（spec 005） */}
          <Route path="album" element={<ComingSoon />} />
          {/* 設定（通知・言語） */}
          <Route path="settings" element={<ComingSoon />} />
          <Route path="*" element={<Navigate to="/family" replace />} />
        </Route>
      </Routes>
    </AreaGuard>
  )
}
