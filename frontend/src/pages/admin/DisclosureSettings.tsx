import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'

type ItemSetting = { code: string; visible: boolean }
type ThemeSetting = { code: string; emoji: string; visible: boolean }
export type Disclosure = { items: ItemSetting[]; themes: ThemeSetting[] }
// 変えたものだけ（code → 見せるか）
export type DisclosureChanges = { items: Record<string, boolean>; themes: Record<string, boolean> }

const QUERY_KEY = ['admin', 'disclosure']

/**
 * 開示設定（UI-A01。spec 001 の T040。`/admin/disclosure`。生活相談員・施設長）。
 * 記録項目とテーマごとに、家族に見せるかを選んで「保存する」（FR-009）。
 * 家族に見えるものが変わるので、押してすぐには保存しない。保存すると、次に家族が開いたときから変わる（FR-012）。
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
    onSuccess: (saved) => queryClient.setQueryData(QUERY_KEY, saved),
  })

  if (disclosure.isPending) return <Message k="layout.loading" />
  if (disclosure.isError) return <Message k={messageKeyOf(disclosure.error)} />
  return (
    <DisclosureForm
      // 保存したら、保存した内容から選び直せるようにする
      key={JSON.stringify(disclosure.data)}
      disclosure={disclosure.data}
      saving={save.isPending}
      saved={save.isSuccess}
      errorKey={save.isError ? messageKeyOf(save.error) : null}
      onSave={(changes) => save.mutate(changes)}
    />
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
  const [changes, setChanges] = useState<DisclosureChanges>({ items: {}, themes: {} })
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
