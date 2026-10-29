import { Navigate, Route, Routes } from 'react-router'
import { DevUserSwitcher } from './components/DevUserSwitcher'
import AdminRoutes from './pages/admin/AdminRoutes'
import FamilyRoutes from './pages/family/FamilyRoutes'
import { useUserLanguage } from './i18n/useUserLanguage'
import { HomeRedirect } from './pages/HomeRedirect'
import { LoginPage } from './pages/LoginPage'
import { Signup } from './pages/signup/Signup'
import { SignupComplete } from './pages/signup/SignupComplete'
import StaffRoutes from './pages/staff/StaffRoutes'

// 画面のまとまりごとに、URL の先頭を分ける（spec 001 の T019・docs/画面設計.md「3」）。
// 中の画面は、それぞれの *Routes.tsx に足す（同じファイルを同時に触らないように）
export default function App() {
  // ログイン中のアカウントの表示言語を、画面の言語にする（001-T084）
  useUserLanguage()

  return (
    <>
      <Routes>
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        {/* ログインなしの申し込み（spec 002 の T027）。施設がすでにあれば、API が 404 を返す */}
        <Route path="/signup" element={<Signup />} />
        <Route path="/signup/complete" element={<SignupComplete />} />
        <Route path="/family/*" element={<FamilyRoutes />} />
        <Route path="/staff/*" element={<StaffRoutes />} />
        <Route path="/admin/*" element={<AdminRoutes />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {/* 開発のときだけ（本番のビルドには入らない） */}
      {import.meta.env.DEV && <DevUserSwitcher />}
    </>
  )
}
