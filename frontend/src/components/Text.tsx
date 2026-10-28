import { useContext } from 'react'
import { useTranslation } from 'react-i18next'
import { FamilyContext } from '../i18n/audience'
import { Ruby } from '../i18n/Ruby'

/**
 * 辞書のキーから、ふりがなつきの文言を出す（`<Ruby text={t(key)} />` の短い書き方）。
 * 中身を 1 つの `<span>` に包んで返す。flex の子に直接置いても、文字とふりがな（`<ruby>`）が
 * 別々の子に分かれて崩れないようにするため（#196。#189 で下のメニューを直したのと同じ原因）。
 * 家族の画面では、辞書に `<キー>_family` があれば、そちらを出す（例：`error.validation_error_family`。#79）。
 * `_family` があるかは、今の言語の辞書だけで確かめる（日本語に戻る設定のせいで、
 * ほかの言語の画面に日本語の文が出ないように）。
 */
export function Text({ k }: { k: string }) {
  const { t, i18n } = useTranslation()
  const isFamily = useContext(FamilyContext)
  const familyKey = `${k}_family`
  const hasFamilyText =
    isFamily && i18n.getResource(i18n.language, 'translation', familyKey) !== undefined
  return (
    <span>
      <Ruby text={t(hasFamilyText ? familyKey : k)} />
    </span>
  )
}
