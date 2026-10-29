import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { stripRuby } from '../i18n/rubyText'

/** ブラウザのタブの題。「画面の題 ｜ YORIS」。画面の題がなければ、アプリの名前だけ（2.4.2）。 */
export function pageTitle(label: string | null | undefined, appName: string): string {
  const name = label ? stripRuby(label).trim() : ''
  return name ? `${name} ｜ ${appName}` : appName
}

/**
 * 画面の枠で呼んで、ブラウザのタブの題を決める（デザインの決めごと 12.3・10 章の 2.4.2。#330）。
 * titleKey は辞書のキー（例：layout.to_staff）。表示言語を切り替えたら、題も変わる。
 */
export function usePageTitle(titleKey?: string) {
  const { t } = useTranslation()
  const title = pageTitle(titleKey ? t(titleKey) : null, stripRuby(t('layout.app_name')))
  useEffect(() => {
    document.title = title
  }, [title])
}
