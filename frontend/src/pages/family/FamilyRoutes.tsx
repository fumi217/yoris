import { Navigate, Route, Routes } from 'react-router'
import { AreaGuard } from '../../components/AreaGuard'
import { ComingSoon } from '../../components/ComingSoon'
import { FamilyContext } from '../../i18n/audience'
import { FuriganaContext } from '../../i18n/furigana'
import { Album } from './Album'
import { ContactBook } from './ContactBook'
import { FamilyLayout } from './FamilyLayout'
import { FamilyMorePage } from './FamilyMorePage'
import { Inquiry } from './Inquiry'
import { Notifications } from './Notifications'
import { Requests } from './Requests'
import { VisitBooking } from './visits/VisitBooking'

/**
 * 家族の画面（/family 以下）。担当は、自分の画面の ComingSoon を差し替える。
 * 家族の画面は、ふりがなを出さない（constitution 3.2.0 の UI 方針の例外。#260）。読み込み中・エラーの文言も含む。
 */
export default function FamilyRoutes() {
  return (
    <FuriganaContext.Provider value={false}>
      <FamilyContext.Provider value={true}>
        <AreaGuard area="family">
          <Routes>
            <Route element={<FamilyLayout />}>
              {/* 連絡帳（ホーム。001-T059 さとこ） */}
              <Route index element={<ContactBook />} />
              {/* 知りたいことを頼む（001-T060 さとこ） */}
              <Route path="requests/*" element={<Requests />} />
              {/* お知らせの一覧（001-T061 さとこ） */}
              <Route path="notifications" element={<Notifications />} />
              <Route path="more" element={<FamilyMorePage />} />
              {/* 面会の予約（003-T014 ゆう） */}
              <Route path="visits" element={<VisitBooking />} />
              {/* お問い合わせ（AI に質問する。004-T020 みさき） */}
              <Route path="inquiry" element={<Inquiry />} />
              {/* アルバム（UI-F06。spec 005 の 005-T012 さとこ） */}
              <Route path="album" element={<Album />} />
              {/* 設定（通知・言語） */}
              <Route path="settings" element={<ComingSoon />} />
              <Route path="*" element={<Navigate to="/family" replace />} />
            </Route>
          </Routes>
        </AreaGuard>
      </FamilyContext.Provider>
    </FuriganaContext.Provider>
  )
}
