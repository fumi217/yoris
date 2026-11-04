import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client'
import { Icon } from '../../components/Icon'
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
    <section className="px-4 pb-4">
      <div className="overflow-hidden rounded-xl border border-card-line bg-card">
        <h2 className="border-b border-card-line px-4 py-2.5 font-bold">
          <Icon name="upload-waiting" className="mr-2 text-primary" />
          <Text k="disclosure.history_title" />
        </h2>
        {rows.length === 0 ? (
          <p className="px-4 py-3 text-sm text-ink-sub">
            <Text k="disclosure.history_empty" />
          </p>
        ) : (
          <ul className="text-sm">
            {rows.map((row) => (
              // いつ・だれが・何をどうしたか（狭い幅では縦に積む）
              <li
                key={row.id}
                className="grid gap-x-3 gap-y-0.5 border-t border-card-line px-4 py-2.5 first:border-t-0 sm:grid-cols-[8rem_7rem_1fr]"
              >
                <span className="text-ink-sub tabular-nums">
                  <Ruby text={t('disclosure.history_when', changedAtParts(row.changed_at))} />
                </span>
                {/* 職員の名前は、辞書を通さずそのまま出す */}
                <span className="font-bold">{row.changed_by_name}</span>
                <span>
                  <Ruby
                    text={t('disclosure.history_change', {
                      target: t(targetLabelKey(row)),
                      value: t(row.new_visible ? 'disclosure.visible' : 'disclosure.hidden'),
                    })}
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
