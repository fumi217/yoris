// 多言語の辞書の仕組み（spec 001 の T016・research.md R-11）。
// 画面の固定の文言は、必ずこの辞書から引く。ミニマム版は日本語だけ（インドネシア語・英語は 001-T082）。
// キーの付け方は README.md のとおり（spec ごとに先頭を分けて、書き足すときにぶつかりにくくする）。
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import ja from './ja.json'

export const SUPPORTED_LANGUAGES = ['ja', 'id', 'en'] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]

void i18n.use(initReactI18next).init({
  resources: { ja: { translation: ja } },
  // 表示言語はログイン中のアカウントの言語で決める（切り替えは 001-T084）。それまでは日本語
  lng: 'ja',
  fallbackLng: 'ja',
  interpolation: {
    // React が表示のときにエスケープするので、i18next では二重にエスケープしない
    escapeValue: false,
  },
  returnNull: false,
})

export default i18n
