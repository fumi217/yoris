import { NavLink, Outlet, useLocation } from 'react-router'
import { useMe } from '../../auth/me'
import { Text } from '../../components/Text'
import { familyMainMenu, familyMoreMenu } from './menu'

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `flex flex-1 flex-col items-center py-2 text-sm ${isActive ? 'font-bold text-sky-700' : 'text-gray-600'}`

/** 家族の画面の枠。上に入居者の呼び名、下にメニュー（3 つ＋「☰ その他」）。 */
export function FamilyLayout() {
  const me = useMe().data
  const { pathname } = useLocation()
  // 「☰ その他」の中の画面（面会など）を開いているときも、「☰ その他」を選ばれた表示にする
  const inMore = familyMoreMenu.some((item) => pathname.startsWith(item.to))

  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col">
      <header className="border-b p-4">
        <p className="text-lg font-bold">{me?.display_name}</p>
      </header>
      <main className="flex-1 pb-20">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 mx-auto flex max-w-xl border-t bg-white">
        {familyMainMenu.map((item) => (
          // 連絡帳（/family）は、ほかの画面を開いているときに選ばれた表示にしない
          <NavLink key={item.to} to={item.to} end={item.to === '/family'} className={tabClass}>
            <span aria-hidden="true">{item.icon}</span>
            {/* 縦に並べる枠の中で、ふりがなと文字が別々の行にならないよう、1 つにまとめる */}
            <span>
              <Text k={item.labelKey} />
            </span>
          </NavLink>
        ))}
        <NavLink
          to="/family/more"
          className={({ isActive }) => tabClass({ isActive: isActive || inMore })}
        >
          <span aria-hidden="true">☰</span>
          <span>
            <Text k="layout.family_menu.more" />
          </span>
        </NavLink>
      </nav>
    </div>
  )
}
