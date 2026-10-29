import { useEffect, useRef, type RefObject } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { useMe } from '../../auth/me'
import { Logo } from '../../components/Logo'
import { Text } from '../../components/Text'
import { usePageTitle } from '../../components/usePageTitle'
import { familyMainMenu, familyMoreMenu, familyTitleKey } from './menu'

// 下は 4 つ＋「☰ その他」なので、360px の幅でも名前が折り返さない大きさにする（PR #213 さとこ）
const tabClass = ({ isActive }: { isActive: boolean }) =>
  `flex flex-1 flex-col items-center py-2 text-xs ${isActive ? 'font-bold text-sky-700' : 'text-gray-600'}`

/** 家族の画面の枠。上の左にロゴ・右に入居者の呼び名、下にメニュー（4 つ＋「☰ その他」）。 */
export function FamilyLayout() {
  const me = useMe().data
  const { pathname } = useLocation()
  // 「☰ その他」の中の画面（面会など）を開いているときも、「☰ その他」を選ばれた表示にする
  const inMore = familyMoreMenu.some((item) => pathname.startsWith(item.to))
  // ブラウザのタブの題：「連絡帳 ｜ YORIS」など（デザインの決めごと 12.3。#330）
  usePageTitle(familyTitleKey(pathname) ?? undefined)
  const menuRef = useRef<HTMLElement>(null)
  useMenuHeight(menuRef)

  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col">
      <header className="flex items-center justify-between gap-3 border-b p-4">
        {/* ロゴを押すと、ホーム（連絡帳）へ。入居者の呼び名は、長いときは省略する（幅 320px でも横にあふれない） */}
        <Link to="/family">
          <Logo className="h-7" />
        </Link>
        <p className="min-w-0 truncate text-lg font-bold">{me?.display_name}</p>
      </header>
      <main className="flex-1 pb-20">
        <Outlet />
      </main>
      <nav
        ref={menuRef}
        className="fixed inset-x-0 bottom-0 mx-auto flex max-w-xl border-t bg-white"
      >
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

/**
 * 下のメニューの高さを測って、CSS の変数 `--family-menu-height` に入れる（キャラクターを、メニューの上に置くため。#339）。
 * 幅が狭い・文字を大きくしたときは、メニューの名前が折り返して高くなるので、決まった値にしない。
 */
function useMenuHeight(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const menu = ref.current
    if (!menu || typeof ResizeObserver === 'undefined') return
    const root = document.documentElement
    const observer = new ResizeObserver(() => {
      root.style.setProperty('--family-menu-height', `${menu.offsetHeight}px`)
    })
    observer.observe(menu)
    return () => {
      observer.disconnect()
      root.style.removeProperty('--family-menu-height')
    }
  }, [ref])
}
