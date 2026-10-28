import { useTranslation } from 'react-i18next'
import { Ruby } from '../i18n/Ruby'

/**
 * 職員の名前のあとに付ける「（職種）」（家族の画面の職員の返事。#263）。
 * 職種は辞書の occupation.* で引く（訳した画面では職種も訳す。かっこも辞書の occupation.paren）。
 * 職種が空なら何も出さない（名前だけ）。役割では補わない（看護師が「介護職員」と出ないように）。
 */
export function OccupationLabel({ code }: { code: string | null }) {
  const { t } = useTranslation()
  if (!code) return null
  return <Ruby text={t('occupation.paren', { occupation: t(`occupation.${code}`) })} />
}
