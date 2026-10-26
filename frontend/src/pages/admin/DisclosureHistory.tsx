import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import {
  changedAtParts,
  HISTORY_QUERY_KEY,
  targetLabelKey,
  type DisclosureHistoryRow,
} from './historyRows'

/**
 * 開示設定の変更履歴（spec 001 の T041・FR-011）。開示設定の画面の下に、新しい順に出す。
 * いつ・誰が・何を（どれを「見せる／見せない」にしたか）。
 */
export function DisclosureHistory() {
  const history = useQuery({
    queryKey: HISTORY_QUERY_KEY,
    queryFn: () => api.get<DisclosureHistoryRow[]>('/api/admin/disclosure/history'),
  })
  // 読めないときは、設定の画面のほうを使えるよう、この欄だけ出さない
  if (!history.data) return null
  return <DisclosureHistoryView rows={history.data} />
}

/** 欄の中身（テストではこれを直接出す）。 */
export function DisclosureHistoryView({ rows }: { rows: DisclosureHistoryRow[] }) {
  const { t } = useTranslation()

  return (
    <section className="space-y-2 p-4">
      <h2 className="font-bold">
        <Text k="disclosure.history_title" />
      </h2>
      {rows.length === 0 ? (
        <p className="text-sm text-gray-600">
          <Text k="disclosure.history_empty" />
        </p>
      ) : (
        <ul className="divide-y border-y text-sm">
          {rows.map((row) => (
            <li key={row.id} className="py-2">
              <span className="mr-2 text-gray-600">
                <Ruby text={t('disclosure.history_when', changedAtParts(row.changed_at))} />
              </span>
              {/* 職員の名前は、辞書を通さずそのまま出す */}
              <span className="mr-2 font-bold">{row.changed_by_name}</span>
              <Ruby
                text={t('disclosure.history_change', {
                  target: t(targetLabelKey(row)),
                  value: t(row.new_visible ? 'disclosure.visible' : 'disclosure.hidden'),
                })}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
