import { useTranslation } from 'react-i18next'
import { Ruby } from '../i18n/Ruby'

/**
 * 辞書のキーから、ふりがなつきの文言を出す（`<Ruby text={t(key)} />` の短い書き方）。
 * 中身を 1 つの `<span>` に包んで返す。flex の子に直接置いても、文字とふりがな（`<ruby>`）が
 * 別々の子に分かれて崩れないようにするため（#196。#189 で下のメニューを直したのと同じ原因）。
 */
export function Text({ k }: { k: string }) {
  const { t } = useTranslation()
  return (
    <span>
      <Ruby text={t(k)} />
    </span>
  )
}
