import { useEffect } from 'react'
import { useLocation } from 'react-router'

// 開発用のユーザー切り替えを隠す印（spec 001 の research.md R-02・#428）。
// ふだんは出す。URL の `?dev=0` で隠し、`?dev=1` で出し直す。隠す印は同じタブの間だけ覚える
const HIDDEN_KEY = 'dev-switcher-hidden'

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

// `sessionStorage` は、使えない環境（プライベートウィンドウなど）で例外になることがある
function sessionStore(): Store | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function readHiddenMark(store: Store | null): boolean {
  try {
    return store?.getItem(HIDDEN_KEY) === '1'
  } catch {
    return false
  }
}

export function saveHiddenMark(store: Store | null, hidden: boolean): void {
  try {
    if (hidden) store?.setItem(HIDDEN_KEY, '1')
    else store?.removeItem(HIDDEN_KEY)
  } catch {
    // 覚えられないときは、そのときの URL だけで決める
  }
}

/** URL の `dev` を優先し、なければ覚えている印に従う（`?dev=0` は隠す、`?dev=1` は出す） */
export function isDevHidden(search: string, marked: boolean): boolean {
  const dev = new URLSearchParams(search).get('dev')
  if (dev === '0') return true
  if (dev === '1') return false
  return marked
}

/** 家族の画面（`/family` の下）は、下のメニューがある */
export function isFamilyPath(pathname: string): boolean {
  return pathname === '/family' || pathname.startsWith('/family/')
}

export function useDevHidden(): boolean {
  const { search } = useLocation()
  const hidden = isDevHidden(search, readHiddenMark(sessionStore()))
  useEffect(() => {
    saveHiddenMark(sessionStore(), hidden)
  }, [hidden])
  return hidden
}
