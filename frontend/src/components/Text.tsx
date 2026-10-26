import { useTranslation } from 'react-i18next'
import { Ruby } from '../i18n/Ruby'

/** 辞書のキーから、ふりがなつきの文言を出す（`<Ruby text={t(key)} />` の短い書き方）。 */
export function Text({ k }: { k: string }) {
  const { t } = useTranslation()
  return <Ruby text={t(k)} />
}
