import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { themeIconName } from '../../components/themeIcon'
import { Icon, type IconName } from '../../components/Icon'
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
type FeatureSetting = { code: string; visible: boolean }
export type Disclosure = {
  items: ItemSetting[]
  themes: ThemeSetting[]
  // 機能（アルバム。spec 005 の 005-T023）
  features: FeatureSetting[]
  // 関係しそうな組み合わせの一覧（T042。backend の RELATED_PAIRS）
  related: RelatedPair[]
}
// 変えたものだけ（code → 見せるか）
export type DisclosureChanges = {
  items: Record<string, boolean>
  themes: Record<string, boolean>
  features: Record<string, boolean>
}
type Kind = keyof DisclosureChanges

const QUERY_KEY = ['admin', 'disclosure']

/**
 * 開示設定（UI-A01。spec 001 の T040。`/admin/disclosure`。生活相談員・施設長）。
 * 記録項目・テーマ・機能（アルバム。spec 005 の 005-T023）ごとに、家族に見せるかを選んで「保存する」（FR-009）。
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
  const [changes, setChanges] = useState<DisclosureChanges>({ items: {}, themes: {}, features: {} })
  // 今の選び方（まだ保存していない変更も含む）
  const isVisible = (kind: 'items' | 'themes', code: string) =>
    changes[kind][code] ?? disclosure[kind].find((row) => row.code === code)?.visible ?? false
  const warnings = warningsFor(disclosure.related, isVisible)
  const dirty = Object.values(changes).some((changed) => Object.keys(changed).length > 0)

  const toggle = (kind: Kind, code: string, original: boolean, visible: boolean) =>
    setChanges((current) => {
      const next = { ...current[kind] }
      // 元に戻したら、変えたものから外す
      if (visible === original) delete next[code]
      else next[code] = visible
      return { ...current, [kind]: next }
    })

  const count = Object.values(changes).reduce(
    (sum, changed) => sum + Object.keys(changed).length,
    0,
  )
  const changedOf = (kind: Kind, code: string) => code in changes[kind]

  return (
    <form
      className="space-y-4 p-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(changes)
      }}
    >
      <div>
        <h1 className="text-2xl font-bold">
          <Text k="disclosure.title" />
        </h1>
        <p className="mt-1 text-sm text-ink-sub">
          <Text k="disclosure.note" />
        </p>
        <p role="status" aria-live="polite" className="mt-2 text-sm empty:hidden">
          {saved && !dirty && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 font-bold text-green-800">
              <Icon name="check" />
              <Text k="disclosure.saved" />
            </span>
          )}
        </p>
      </div>

      <Section icon="contact-book" titleKey="disclosure.items">
        {disclosure.items.map((item) => (
          <Row
            key={item.code}
            name={`item-${item.code}`}
            icon={ITEM_ICONS[item.code]}
            labelKey={`disclosure.item.${item.code}`}
            visible={changes.items[item.code] ?? item.visible}
            changed={changedOf('items', item.code)}
            onChange={(visible) => toggle('items', item.code, item.visible, visible)}
          />
        ))}
      </Section>

      <Section icon="requests" titleKey="disclosure.themes">
        {disclosure.themes.map((theme) => (
          <Row
            key={theme.code}
            name={`theme-${theme.code}`}
            icon={themeIconName(theme.code)}
            labelKey={theme.code}
            visible={changes.themes[theme.code] ?? theme.visible}
            changed={changedOf('themes', theme.code)}
            onChange={(visible) => toggle('themes', theme.code, theme.visible, visible)}
          />
        ))}
      </Section>

      <Section icon="album" titleKey="disclosure.features">
        {disclosure.features.map((feature) => (
          <Row
            key={feature.code}
            name={`feature-${feature.code}`}
            icon={FEATURE_ICONS[feature.code]}
            labelKey={`disclosure.feature.${feature.code}`}
            visible={changes.features[feature.code] ?? feature.visible}
            changed={changedOf('features', feature.code)}
            onChange={(visible) => toggle('features', feature.code, feature.visible, visible)}
          />
        ))}
      </Section>

      {warnings.length > 0 && (
        <ul className="space-y-1 rounded-xl border border-amber-300 bg-amber-100 px-4 py-3 text-sm font-semibold text-amber-800">
          {warnings.map((pair) => (
            <li key={`${pair.item}-${pair.theme}`}>
              <Icon name="warning" className="mr-1.5" />
              <Ruby
                text={t('disclosure.warning', {
                  item: t(`disclosure.item.${pair.item}`),
                  theme: t(pair.theme),
                })}
              />
            </li>
          ))}
        </ul>
      )}

      {/* 変えたときだけ、下に保存の帯を出す（家族の通知の設定と同じ形。#452）。家族に見えるものが変わるので、
          押してすぐには保存しない */}
      {(dirty || saving || errorKey) && (
        <div className="sticky bottom-0 -mx-4 -mb-4 space-y-1 border-t border-card-line bg-card px-4 py-2.5 shadow-[0_-4px_12px_rgb(15_31_61/0.08)]">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <p className="min-w-0 flex-1 basis-60 text-sm font-bold text-primary-dark">
              {dirty && <Ruby text={t('disclosure.unsaved_count', { count })} />}
            </p>
            {dirty && (
              <button
                type="button"
                disabled={saving}
                onClick={() => setChanges({ items: {}, themes: {}, features: {} })}
                className="min-h-11 rounded-lg border border-primary bg-card px-4 font-bold text-primary-dark disabled:opacity-50"
              >
                <Text k="disclosure.revert" />
              </button>
            )}
            <button
              type="submit"
              disabled={!dirty || saving}
              className="min-h-11 rounded-lg bg-primary px-5 font-bold text-white disabled:opacity-50"
            >
              <Text k={saving ? 'disclosure.saving' : 'disclosure.save'} />
            </button>
          </div>
          {errorKey && (
            <p role="alert" className="text-sm font-bold text-red-700">
              <Text k={errorKey} />
            </p>
          )}
        </div>
      )}
    </form>
  )
}

function Section({
  icon,
  titleKey,
  children,
}: {
  icon: IconName
  titleKey: string
  children: ReactNode
}) {
  return (
    <fieldset className="overflow-hidden rounded-xl border border-card-line bg-card">
      <legend className="sr-only">
        <Text k={titleKey} />
      </legend>
      {/* legend は枠の線の上に出るので、見える見出しは別に置く（読み上げは legend） */}
      <p aria-hidden="true" className="border-b border-card-line px-4 py-2.5 font-bold">
        <Icon name={icon} className="mr-2 text-primary" />
        <Text k={titleKey} />
      </p>
      <ul>{children}</ul>
    </fieldset>
  )
}

const ITEM_ICONS: Record<string, IconName> = {
  meal: 'meal',
  mood: 'mood',
  sleep: 'sleep',
  memo: 'memo',
}
const FEATURE_ICONS: Record<string, IconName> = { album: 'album' }

type RowProps = {
  name: string
  // まだ保存していない変更か
  changed: boolean
  labelKey: string
  icon?: IconName
  visible: boolean
  onChange: (visible: boolean) => void
}

/**
 * 1 行：名前と、「見せる／見せない」のつまみ（`role="switch"`。#452）。
 * つまみの色・位置に加えて、横に「見せる」「見せない」の文字を出す（色だけに頼らない）。
 * まだ保存していない変更の行は、左の線と「変更」の印で示す。
 */
function Row({ name, labelKey, icon, visible, changed, onChange }: RowProps) {
  return (
    <li
      className={`border-t border-card-line first:border-t-0 ${
        changed ? 'shadow-[inset_3px_0_0_var(--color-primary)]' : ''
      }`}
    >
      <label className="flex min-h-14 cursor-pointer items-center gap-2 px-4 py-2">
        <span className="min-w-0 flex-1">
          {icon && <Icon name={icon} className="mr-2 text-ink-sub" />}
          <Text k={labelKey} />
          {changed && (
            <span className="ml-2 rounded bg-primary-soft px-2 py-0.5 text-xs font-bold text-primary-dark">
              <Text k="disclosure.changed" />
            </span>
          )}
        </span>
        <span
          className={`w-16 shrink-0 text-right text-sm font-bold ${visible ? 'text-primary-dark' : 'text-gray-600'}`}
          aria-hidden="true"
        >
          <Text k={visible ? 'disclosure.visible' : 'disclosure.hidden'} />
        </span>
        <input
          type="checkbox"
          role="switch"
          name={name}
          className="peer sr-only"
          checked={visible}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span
          aria-hidden="true"
          className="relative h-[28px] w-[46px] shrink-0 rounded-full bg-field-line transition-colors peer-checked:bg-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary after:absolute after:top-[3px] after:left-[3px] after:size-[22px] after:rounded-full after:bg-white after:shadow after:transition-[left] peer-checked:after:left-[21px]"
        />
      </label>
    </li>
  )
}
