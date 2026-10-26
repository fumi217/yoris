import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { DisclosureHistory } from './DisclosureHistory'
import { warningsFor, type RelatedPair } from './disclosureRules'
import { HISTORY_QUERY_KEY } from './historyRows'

type ItemSetting = { code: string; visible: boolean }
type ThemeSetting = { code: string; emoji: string; visible: boolean }
export type Disclosure = {
  items: ItemSetting[]
  themes: ThemeSetting[]
  // 関係しそうな組み合わせの一覧（T042。backend の RELATED_PAIRS）
  related: RelatedPair[]
}
// 変えたものだけ（code → 見せるか）
export type DisclosureChanges = { items: Record<string, boolean>; themes: Record<string, boolean> }

const QUERY_KEY = ['admin', 'disclosure']

/**
 * 開示設定（UI-A01。spec 001 の T040。`/admin/disclosure`。生活相談員・施設長）。
 * 記録項目とテーマごとに、家族に見せるかを選んで「保存する」（FR-009）。
 * 家族に見えるものが変わるので、押してすぐには保存しない。保存すると、次に家族が開いたときから変わる（FR-012）。
 * 下に、変更の履歴（いつ・誰が・何を。FR-011・T041）を出す。
 */
export function DisclosureSettings() {
  const queryClient = useQueryClient()
  const disclosure = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => api.get<Disclosure>('/api/admin/disclosure'),
  })
  const save = useMutation({
    mutationFn: (changes: DisclosureChanges) =>
      api.put<Disclosure>('/api/admin/disclosure', changes),
    onSuccess: (saved) => {
      queryClient.setQueryData(QUERY_KEY, saved)
      void queryClient.invalidateQueries({ queryKey: HISTORY_QUERY_KEY })
    },
  })

  if (disclosure.isPending) return <Message k="layout.loading" />
  if (disclosure.isError) return <Message k={messageKeyOf(disclosure.error)} />
  return (
    <>
      <DisclosureForm
        // 保存したら、保存した内容から選び直せるようにする
        key={JSON.stringify(disclosure.data)}
        disclosure={disclosure.data}
        saving={save.isPending}
        saved={save.isSuccess}
        errorKey={save.isError ? messageKeyOf(save.error) : null}
        onSave={(changes) => save.mutate(changes)}
      />
      <DisclosureHistory />
    </>
  )
}

type FormProps = {
  disclosure: Disclosure
  saving: boolean
  saved: boolean
  errorKey: string | null
  onSave: (changes: DisclosureChanges) => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function DisclosureForm({ disclosure, saving, saved, errorKey, onSave }: FormProps) {
  const { t } = useTranslation()
  const [changes, setChanges] = useState<DisclosureChanges>({ items: {}, themes: {} })
  // 今の選び方（まだ保存していない変更も含む）
  const isVisible = (kind: 'items' | 'themes', code: string) =>
    changes[kind][code] ?? disclosure[kind].find((row) => row.code === code)?.visible ?? false
  const warnings = warningsFor(disclosure.related, isVisible)
  const themeEmoji = (code: string) =>
    disclosure.themes.find((theme) => theme.code === code)?.emoji ?? ''
  const dirty = Object.keys(changes.items).length + Object.keys(changes.themes).length > 0

  const toggle = (kind: 'items' | 'themes', code: string, original: boolean, visible: boolean) =>
    setChanges((current) => {
      const next = { ...current[kind] }
      // 元に戻したら、変えたものから外す
      if (visible === original) delete next[code]
      else next[code] = visible
      return { ...current, [kind]: next }
    })

  return (
    <form
      className="space-y-6 p-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(changes)
      }}
    >
      <div>
        <h1 className="text-xl font-bold">
          <Text k="disclosure.title" />
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          <Text k="disclosure.note" />
        </p>
      </div>

      <Section titleKey="disclosure.items">
        {disclosure.items.map((item) => (
          <Row
            key={item.code}
            name={`item-${item.code}`}
            labelKey={`disclosure.item.${item.code}`}
            visible={changes.items[item.code] ?? item.visible}
            onChange={(visible) => toggle('items', item.code, item.visible, visible)}
          />
        ))}
      </Section>

      <Section titleKey="disclosure.themes">
        {disclosure.themes.map((theme) => (
          <Row
            key={theme.code}
            name={`theme-${theme.code}`}
            icon={theme.emoji}
            labelKey={theme.code}
            visible={changes.themes[theme.code] ?? theme.visible}
            onChange={(visible) => toggle('themes', theme.code, theme.visible, visible)}
          />
        ))}
      </Section>

      {warnings.length > 0 && (
        // 止めはしない。注意書きだけを出す（FR-009「連動させない」）
        <ul className="space-y-1 rounded border border-orange-700 bg-orange-50 p-3 text-sm">
          {warnings.map((pair) => (
            <li key={`${pair.item}-${pair.theme}`}>
              <span aria-hidden="true">⚠️ </span>
              <Ruby
                text={t('disclosure.warning', {
                  item: t(`disclosure.item.${pair.item}`),
                  theme: `${themeEmoji(pair.theme)} ${t(pair.theme)}`,
                })}
              />
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2">
        <p role="status" aria-live="polite" className="min-h-6 text-sm">
          {errorKey ? (
            <span className="text-red-700">
              <Text k={errorKey} />
            </span>
          ) : dirty ? (
            <span className="text-orange-700">
              <Text k="disclosure.unsaved" />
            </span>
          ) : (
            saved && <Text k="disclosure.saved" />
          )}
        </p>
        <button
          type="submit"
          disabled={!dirty || saving}
          className="w-full rounded bg-sky-700 p-3 text-lg font-bold text-white disabled:opacity-50"
        >
          <Text k={saving ? 'disclosure.saving' : 'disclosure.save'} />
        </button>
      </div>
    </form>
  )
}

function Section({ titleKey, children }: { titleKey: string; children: ReactNode }) {
  return (
    <fieldset>
      <legend className="mb-2 font-bold">
        <Text k={titleKey} />
      </legend>
      <ul className="divide-y border-y">{children}</ul>
    </fieldset>
  )
}

type RowProps = {
  name: string
  labelKey: string
  icon?: string
  visible: boolean
  onChange: (visible: boolean) => void
}

/** 1 行：名前と「見せる／見せない」の 2 つのボタン（どちらを選んでいるか、色と文字で分かる）。 */
function Row({ name, labelKey, icon, visible, onChange }: RowProps) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-2">
      <span>
        {icon && <span aria-hidden="true">{icon} </span>}
        <Text k={labelKey} />
      </span>
      <span className="flex gap-2">
        {[true, false].map((value) => (
          <label
            key={String(value)}
            className={`cursor-pointer rounded border-2 px-3 py-1 ${
              visible === value
                ? value
                  ? 'border-sky-700 bg-sky-700 text-white'
                  : 'border-gray-700 bg-gray-700 text-white'
                : 'border-gray-300'
            }`}
          >
            <input
              type="radio"
              name={name}
              className="sr-only"
              checked={visible === value}
              onChange={() => onChange(value)}
            />
            <Text k={value ? 'disclosure.visible' : 'disclosure.hidden'} />
          </label>
        ))}
      </span>
    </li>
  )
}
