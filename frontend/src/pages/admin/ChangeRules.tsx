import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { ConfirmButton } from '../../components/ConfirmButton'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { changedAtParts } from './historyRows'
import { visibleSaved } from './savedRule'

export type ChangeRule = { code: string; enabled: boolean }
/** `GET /api/admin/change-rules/history` の 1 件（backend/app/api/admin/change_rules.py の RuleHistoryOut）。 */
export type ChangeRuleHistoryRow = {
  id: number
  rule_code: string
  enabled_before: boolean
  enabled_after: boolean
  changed_by_name: string
  changed_at: string
}

const RULES_KEY = ['admin', 'change-rules']
// 履歴のキーは、決まりのキーの前方一致に入る。保存のあとの `invalidateQueries({ queryKey: RULES_KEY })` が、
// 両方を取り直して、両方が終わるまで待つ（キーを変えるときは、この関係を保つ）
const HISTORY_KEY = ['admin', 'change-rules', 'history']

/**
 * 変化の目印の設定（spec 006 の 006-T021・FR-011。`/admin/change-rules`。生活相談員・施設長）。
 * 決まり 3 つを、施設全体でオン／オフする。目印は職員だけが見るもので、家族には出ないので、
 * 開示設定と違い、切り替えたらすぐ保存する（保存のボタンはない）。
 * 下に、変更の履歴（いつ・誰が・どの決まりを・どう変えたか）を新しい順に出す。
 */
export function ChangeRules() {
  const queryClient = useQueryClient()
  const rules = useQuery({
    queryKey: RULES_KEY,
    queryFn: () => api.get<ChangeRule[]>('/api/admin/change-rules'),
  })
  const history = useQuery({
    queryKey: HISTORY_KEY,
    queryFn: () => api.get<ChangeRuleHistoryRow[]>('/api/admin/change-rules/history'),
  })
  const save = useMutation({
    mutationFn: ({ code, enabled }: { code: string; enabled: boolean }) =>
      api.put<ChangeRule>(`/api/admin/change-rules/${encodeURIComponent(code)}`, { enabled }),
    // 画面が古くても、サーバーのいまの値で選び直す（同じ値なら、サーバーは何もしない。R-07）。
    // 取り直しが終わるまで、保存は終わらない扱いにする（古い値のまま押せるようにならないように）
    onSettled: () => queryClient.invalidateQueries({ queryKey: RULES_KEY }),
  })

  if (rules.isPending) return <Message k="layout.loading" />
  // 取り直しだけが失敗したとき（ネットワークの一瞬の不調など）は、いまあるデータの画面を残す
  if (rules.isError && !rules.data) return <Message k={messageKeyOf(rules.error)} />
  return (
    <ChangeRulesView
      rules={rules.data}
      // 読めないときは、設定のほうを使えるよう、履歴の欄だけ出さない
      history={history.data ?? null}
      savingCode={save.isPending ? save.variables.code : null}
      saved={visibleSaved(rules.data, save.isSuccess ? save.data : null)}
      errorKey={save.isError ? messageKeyOf(save.error) : null}
      onChange={(code, enabled) => save.mutate({ code, enabled })}
    />
  )
}

type ViewProps = {
  rules: ChangeRule[]
  history: ChangeRuleHistoryRow[] | null
  savingCode: string | null
  /** 最後に保存できた決まりと、そのときの値。なければ null */
  saved: { code: string; enabled: boolean } | null
  errorKey: string | null
  onChange: (code: string, enabled: boolean) => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function ChangeRulesView({
  rules,
  history,
  savingCode,
  saved,
  errorKey,
  onChange,
}: ViewProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-6 p-4">
      <div>
        <h1 className="text-xl font-bold">
          <Text k="admin.change_rules.title" />
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          <Text k="admin.change_rules.note" />
        </p>
        <p className="mt-1 text-sm text-gray-600">
          <Text k="admin.change_rules.note_off" />
        </p>
      </div>

      <ul className="divide-y border-y">
        {rules.map((rule) => {
          const nameId = `rule-name-${rule.code}`
          const saving = savingCode !== null
          // 保存中は、フォーカスのあるラジオを `disabled` にしない（キーボードで操作する人のフォーカスが
          // 外れるため。WCAG 2.4.3）。代わりに `aria-disabled` にして、保存中の選び直しは受け付けない
          const select = (enabled: boolean) => {
            if (!saving) onChange(rule.code, enabled)
          }
          return (
            <li key={rule.code} className="flex flex-wrap items-center justify-between gap-2 py-3">
              <span id={nameId}>
                <RuleName prefix="admin.change_rules.rule" code={rule.code} />
              </span>
              {/* どの決まりのボタンかが、読み上げに伝わるよう、決まりの名前でグループにする（1.3.1・4.1.2） */}
              <span role="group" aria-labelledby={nameId} className="flex gap-2">
                <RuleChoice rule={rule} value={true} saving={saving} onSelect={select} />
                {rule.enabled ? (
                  // オフにすると、確かめ済みの目印も消える。取り返しにくいので、2 回押して決める
                  <ConfirmButton
                    labelKey="admin.change_rules.off"
                    confirmKey="admin.change_rules.off_confirm"
                    onConfirm={() => select(false)}
                    // 保存中は押せない（確かめたのに、何も起きずに元に戻る、ということがないように）
                    disabled={saving}
                    className={`${CHOICE_BASE} border-gray-500`}
                  />
                ) : (
                  <RuleChoice rule={rule} value={false} saving={saving} onSelect={select} />
                )}
              </span>
            </li>
          )
        })}
      </ul>

      <p role="status" aria-live="polite" className="min-h-6 text-sm">
        {errorKey ? (
          <span className="text-red-700">
            <Text k={errorKey} />
          </span>
        ) : savingCode ? (
          <Text k="admin.change_rules.saving" />
        ) : (
          saved && (
            <Ruby
              text={t(
                saved.enabled ? 'admin.change_rules.saved_on' : 'admin.change_rules.saved_off',
                {
                  rule: t(`admin.change_rules.rule_short.${saved.code}`, {
                    defaultValue: saved.code,
                  }),
                },
              )}
            />
          )
        )}
      </p>

      {history && <ChangeRuleHistory rows={history} />}
    </div>
  )
}

function ChangeRuleHistory({ rows }: { rows: ChangeRuleHistoryRow[] }) {
  const { t } = useTranslation()
  return (
    <section className="space-y-2">
      <h2 className="font-bold">
        <Text k="admin.change_rules.history_title" />
      </h2>
      {rows.length === 0 ? (
        <p className="text-sm text-gray-600">
          <Text k="admin.change_rules.history_empty" />
        </p>
      ) : (
        <ul className="divide-y border-y text-sm">
          {rows.map((row) => (
            <li key={row.id} className="py-2">
              <span className="mr-2 text-gray-600">
                <Ruby text={t('admin.change_rules.history_when', changedAtParts(row.changed_at))} />
              </span>
              {/* 職員の名前は、辞書を通さずそのまま出す */}
              <span className="mr-2 font-bold">{row.changed_by_name}</span>
              <Ruby
                text={t('admin.change_rules.history_change', {
                  rule: t(`admin.change_rules.rule_short.${row.rule_code}`, {
                    defaultValue: row.rule_code,
                  }),
                  value: t(row.enabled_after ? 'admin.change_rules.on' : 'admin.change_rules.off'),
                })}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** 決まりの名前。辞書にないコード（バックエンドで足した決まり）は、コードのまま出す。 */
function RuleName({ prefix, code }: { prefix: string; code: string }) {
  const { i18n } = useTranslation()
  const key = `${prefix}.${code}`
  return i18n.exists(key) ? <Text k={key} /> : <span>{code}</span>
}

// 押す部品は 44px 以上（デザインの決めごと 4 章）。オンとオフは同じ幅にして、行ごとに位置がずれないようにする。フォーカスの枠は、白の上で 3:1 以上の濃さにする
const CHOICE_BASE =
  'inline-flex min-h-11 min-w-20 items-center justify-center rounded border-2 px-4 py-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700'

/** オン／オフの選び方の 1 つ。選ばれている側は、色だけでなく、太字でも示す（デザインの決めごと 5 章）。 */
function RuleChoice({
  rule,
  value,
  saving,
  onSelect,
}: {
  rule: ChangeRule
  value: boolean
  saving: boolean
  onSelect: (enabled: boolean) => void
}) {
  const selected = rule.enabled === value
  return (
    <label
      className={`${CHOICE_BASE} cursor-pointer focus-within:ring-2 focus-within:ring-sky-700 focus-within:ring-offset-2 ${
        selected
          ? `font-bold text-white ${value ? 'border-sky-700 bg-sky-700' : 'border-gray-700 bg-gray-700'}`
          : 'border-gray-500'
      } ${saving ? 'cursor-wait opacity-60' : ''}`}
    >
      <input
        type="radio"
        name={`rule-${rule.code}`}
        className="sr-only"
        checked={selected}
        aria-disabled={saving}
        onChange={() => onSelect(value)}
      />
      <Text k={value ? 'admin.change_rules.on' : 'admin.change_rules.off'} />
    </label>
  )
}
