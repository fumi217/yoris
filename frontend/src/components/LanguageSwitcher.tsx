import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, messageKeyOf } from '../api/client'
import { ME_QUERY_KEY, useMe, type Me } from '../auth/me'
import { SUPPORTED_LANGUAGES, isLanguage, type Language } from '../i18n'
import { Text } from './Text'

// 言語の名前は、その言語で書く（今の表示言語がわからなくても選べるように）。辞書には入れない
const LANGUAGE_NAMES: Record<Language, string> = {
  ja: '日本語',
  id: 'Bahasa Indonesia',
  en: 'English',
}

/**
 * 表示言語の切り替え（spec 001 の T084・FR-021）。職員の画面・管理画面の上の部分と、家族の「その他」に置く。
 * 選ぶとアカウントの言語を保存し、ログイン中の人を入れ替える（画面の言語は useUserLanguage が追いかける）。
 */
export function LanguageSwitcher({ className }: { className?: string }) {
  const queryClient = useQueryClient()
  const me = useMe().data
  const [errorKey, setErrorKey] = useState<string | null>(null)

  if (!me) return null

  async function onChange(value: string) {
    if (!isLanguage(value)) return
    setErrorKey(null)
    try {
      const updated = await api.put<Me>('/api/me/language', { language: value })
      queryClient.setQueryData(ME_QUERY_KEY, updated)
    } catch (error) {
      setErrorKey(messageKeyOf(error))
    }
  }

  return (
    <>
      <select
        aria-label="Language"
        value={me.language}
        onChange={(event) => void onChange(event.target.value)}
        className={className}
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <option key={language} value={language}>
            {LANGUAGE_NAMES[language]}
          </option>
        ))}
      </select>
      {errorKey && (
        <span role="alert" className="text-red-700">
          <Text k={errorKey} />
        </span>
      )}
    </>
  )
}
