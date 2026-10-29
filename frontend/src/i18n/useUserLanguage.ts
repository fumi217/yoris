// ログイン中のアカウントの表示言語を、画面の言語に反映する（spec 001 の T084・FR-021）。
import { useEffect } from 'react'
import { useMe } from '../auth/me'
import i18n, { isLanguage } from './index'

/** App の上のほうで 1 回だけ呼ぶ。ログインしていない間は日本語。 */
export function useUserLanguage() {
  const language = useMe().data?.language
  const next = language && isLanguage(language) ? language : 'ja'

  useEffect(() => {
    void i18n.changeLanguage(next)
    document.documentElement.lang = next
  }, [next])
}
