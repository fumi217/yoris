// 多言語の辞書の仕組み（spec 001 の T016・research.md R-11）。
// 画面の固定の文言は、必ずこの辞書から引く。インドネシア語・英語の辞書は 001-T082 で足している途中で、
// まだ無いキーは日本語が出る（fallbackLng）。
// キーの付け方は README.md のとおり（spec ごとに先頭を分けて、書き足すときにぶつかりにくくする）。
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import id from './id.json'
import ja from './ja.json'

export const SUPPORTED_LANGUAGES = ['ja', 'id', 'en'] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]

export function isLanguage(value: string): value is Language {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(value)
}

void i18n.use(initReactI18next).init({
  resources: { ja: { translation: ja }, id: { translation: id }, en: { translation: en } },
  // 表示言語はログイン中のアカウントの言語で決める（useUserLanguage。切り替えは LanguageSwitcher）。
  // ログインする前は日本語
  lng: 'ja',
  fallbackLng: 'ja',
  interpolation: {
    // React が表示のときにエスケープするので、i18next では二重にエスケープしない
    escapeValue: false,
  },
  returnNull: false,
})

export default i18n
