import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Icon, type IconName } from '../../components/Icon'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import {
  FREQUENCIES,
  isChanged,
  selectableItems,
  toDraft,
  toggleItem,
  type NotificationSettingsData,
  type SettingsDraft,
} from './notificationSettingsView'

const SETTINGS_URL = '/api/family/notification-settings'
const SETTINGS_KEY = ['family', 'notification-settings'] as const

/**
 * 家族の通知設定（spec 001 の 001-T064・FR-023）。`/family/settings`
 * 返事のお知らせ・まとめに入れる記録項目・まとめを送る頻度を選び、「保存する」で保存する
 * （選んだだけでは保存しない。押し間違いを、保存の前に直せるように）。
 * 送り先のメールアドレス（ログイン用と同じ）を出す。選べる項目は、いま開示されているものだけ。
 * 緊急のときは電話で知らせる、という案内を、いつも出す（FR-028）。
 */
export function NotificationSettings() {
  const settings = useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: () => api.get<NotificationSettingsData>(SETTINGS_URL),
  })

  if (settings.isPending) return <Message k="layout.loading" />
  if (settings.isError) return <Message k={messageKeyOf(settings.error)} />
  return <SettingsEditor settings={settings.data} />
}

/** 選んでいる途中の内容を持つ。保存した設定が読めてから出す（初めの値を、ここで決める）。 */
function SettingsEditor({ settings }: { settings: NotificationSettingsData }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<SettingsDraft>(() => toDraft(settings))
  const [saved, setSaved] = useState(false)

  const save = useMutation({
    mutationFn: (body: SettingsDraft) => api.put<NotificationSettingsData>(SETTINGS_URL, body),
    onSuccess: (data) => {
      queryClient.setQueryData(SETTINGS_KEY, data)
      setSaved(true)
    },
  })

  const change = (next: SettingsDraft) => {
    setDraft(next)
    setSaved(false)
    save.reset()
  }

  return (
    <>
      {/* 「その他」から開く画面なので、上に戻るリンク（#449） */}
      <Link
        to="/family/more"
        className="mx-4 mt-2 -mb-3 inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary"
      >
        <Icon name="prev" />
        <Text k="notification_settings.back" />
      </Link>
      <NotificationSettingsView
        settings={settings}
        draft={draft}
        saving={save.isPending}
        saved={saved}
        errorKey={save.isError ? messageKeyOf(save.error) : null}
        onChange={change}
        onSave={() => save.mutate(draft)}
      />
    </>
  )
}

type ViewProps = {
  settings: NotificationSettingsData
  draft: SettingsDraft
  saving: boolean
  saved: boolean
  errorKey: string | null
  onChange: (draft: SettingsDraft) => void
  onSave: () => void
}

// 項目ごとの小さなアイコン（記録の項目・様子のメモ・アルバム）
const ITEM_ICON: Record<string, IconName> = {
  meal: 'meal',
  mood: 'mood',
  sleep: 'sleep',
  memo: 'memo',
}

/** 画面の中身（テストではこれを直接出す）。 */
export function NotificationSettingsView({
  settings,
  draft,
  saving,
  saved,
  errorKey,
  onChange,
  onSave,
}: ViewProps) {
  const items = selectableItems(settings.available_items)
  const changed = isChanged(toDraft(settings), draft)
  // アルバムを見せない設定のとき（API がキーを省略して返す。draft では null）は、項目を出さない
  const albumShown = typeof draft.notify_album === 'boolean'

  return (
    <section className="space-y-4 p-4">
      <div>
        <h1 className="text-2xl font-bold">
          <Text k="notification_settings.title" />
        </h1>
        <p className="mt-1 text-sm text-ink-sub">
          <Text k="notification_settings.intro" />
        </p>
        <p role="status" className="mt-2 empty:hidden">
          {saved && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 text-sm font-bold text-green-800">
              <Icon name="check" />
              <Text k="notification_settings.saved" />
            </span>
          )}
        </p>
      </div>

      <SettingsCard icon="notice-reply" titleKey="notification_settings.reply_title">
        <Toggle
          icon="notifications"
          labelKey="notification_settings.reply_label"
          checked={draft.notify_reply}
          onChange={(checked) => onChange({ ...draft, notify_reply: checked })}
        />
      </SettingsCard>

      <SettingsCard
        icon="contact-book"
        titleKey="notification_settings.items_title"
        hintKey="notification_settings.items_hint"
      >
        {items.length === 0 && !albumShown ? (
          <p className="py-2 text-ink-sub">
            <Text k="notification_settings.items_empty" />
          </p>
        ) : (
          <>
            {items.map((item) => (
              <Toggle
                key={item}
                icon={ITEM_ICON[item] ?? 'contact-book'}
                labelKey={`notification_settings.item.${item}`}
                checked={draft.notify_items.includes(item)}
                onChange={(checked) =>
                  onChange({
                    ...draft,
                    notify_items: toggleItem(draft.notify_items, item, checked),
                  })
                }
              />
            ))}
            {typeof draft.notify_album === 'boolean' && (
              <Toggle
                icon="album"
                labelKey="notification_settings.album_item"
                checked={draft.notify_album}
                onChange={(checked) => onChange({ ...draft, notify_album: checked })}
              />
            )}
          </>
        )}
      </SettingsCard>

      <SettingsCard icon="date" titleKey="notification_settings.frequency_title">
        <div className="space-y-2 pt-1 pb-1.5">
          {FREQUENCIES.map((frequency) => {
            const on = draft.frequency === frequency
            return (
              <label
                key={frequency}
                className={`flex min-h-15 cursor-pointer items-center gap-3 rounded-2xl border-2 px-3 py-2 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary ${
                  on ? 'border-primary bg-primary-soft' : 'border-card-line'
                }`}
              >
                <input
                  type="radio"
                  name="frequency"
                  className="sr-only"
                  checked={on}
                  onChange={() => onChange({ ...draft, frequency })}
                />
                {/* 選んだものは、青の丸と ✓・薄い青の背景・青の枠・太字で示す（色だけに頼らない） */}
                <span
                  aria-hidden="true"
                  className={`flex size-6 shrink-0 items-center justify-center rounded-full border-2 text-xs ${
                    on ? 'border-primary bg-primary text-white' : 'border-field-line bg-card'
                  }`}
                >
                  {on && <Icon name="check" />}
                </span>
                <span className="min-w-0 leading-snug">
                  <span className={`block ${on ? 'font-bold text-primary-dark' : 'font-semibold'}`}>
                    <Text k={`notification_settings.frequency.${frequency}`} />
                  </span>
                  <span className="block text-sm text-ink-sub">
                    <Text k={`notification_settings.frequency_hint.${frequency}`} />
                  </span>
                </span>
              </label>
            )
          })}
        </div>
      </SettingsCard>

      <SettingsCard icon="family-message" titleKey="notification_settings.email_title">
        {/* 送り先のメールアドレス。画面の文字として、そのまま出す（辞書を通さない） */}
        <p className="mt-1 rounded-xl bg-page px-3 py-2.5 font-bold break-all">{settings.email}</p>
        <p className="py-2 text-sm text-ink-sub">
          <Text k="notification_settings.email_hint" />
        </p>
      </SettingsCard>

      {/* 緊急の連絡は、メールやお知らせではなく、電話で行う（FR-028）。いつも出す（連絡帳と同じ淡い青の帯） */}
      <p className="flex items-center gap-3 rounded-xl bg-primary-soft p-4 text-sm font-bold">
        <Icon name="phone" className="text-lg text-primary" />
        <Text k="contact_book.emergency" />
      </p>

      {/* 変えたときだけ、下のメニューの上に保存の帯を出す（押し忘れを防ぐ。#449） */}
      {(changed || saving || errorKey) && (
        <div className="sticky bottom-[var(--family-menu-height)] -mx-4 -mb-4 space-y-1 border-t border-card-line bg-card px-4 py-2.5 shadow-[0_-4px_12px_rgb(15_31_61/0.08)]">
          <div className="flex items-center gap-3">
            <p className="flex-1 text-sm font-bold text-primary-dark">
              {changed && !saving && (
                <>
                  <Icon name="info" className="mr-1.5" />
                  <Text k="notification_settings.changed_short" />
                </>
              )}
            </p>
            <button
              type="button"
              className="min-h-12 rounded-xl bg-primary px-6 font-bold text-white disabled:opacity-60"
              disabled={saving}
              onClick={onSave}
            >
              <Text k={saving ? 'notification_settings.saving' : 'notification_settings.save'} />
            </button>
          </div>
          {errorKey && (
            <p role="alert" className="text-sm font-bold text-red-800">
              <Text k={errorKey} />
            </p>
          )}
        </div>
      )}
    </section>
  )
}

/** まとまりの白い面（丸いアイコン・見出し・ひとこと）。 */
function SettingsCard({
  icon,
  titleKey,
  hintKey,
  children,
}: {
  icon: IconName
  titleKey: string
  hintKey?: string
  children: ReactNode
}) {
  const id = `settings-${titleKey.split('.').pop()}`
  return (
    <section
      aria-labelledby={id}
      className="rounded-2xl border border-card-line bg-card px-4 pt-3.5 pb-1.5"
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary"
        >
          <Icon name={icon} className="text-lg" />
        </span>
        <h2 id={id} className="text-lg font-bold">
          <Text k={titleKey} />
        </h2>
      </div>
      {hintKey && (
        <p className="mt-1 ml-13 text-sm text-ink-sub">
          <Text k={hintKey} />
        </p>
      )}
      <div className="divide-y divide-card-line">{children}</div>
    </section>
  )
}

/**
 * オン・オフのつまみ（`role="switch"`。読み上げは「スイッチ、オン／オフ」）。
 * 色に加えて、つまみの位置（右がオン）でも示す（1.4.1）。行全体を押せる（ラベル）。
 */
function Toggle({
  icon,
  labelKey,
  checked,
  onChange,
}: {
  icon: IconName
  labelKey: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex min-h-14 cursor-pointer items-center gap-3 py-2">
      <span
        aria-hidden="true"
        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-page text-ink-sub"
      >
        <Icon name={icon} />
      </span>
      <span className="min-w-0 flex-1 font-semibold">
        <Text k={labelKey} />
      </span>
      <input
        type="checkbox"
        role="switch"
        className="peer sr-only"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span
        aria-hidden="true"
        className="relative h-[30px] w-[50px] shrink-0 rounded-full bg-field-line transition-colors peer-checked:bg-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary after:absolute after:top-[3px] after:left-[3px] after:size-6 after:rounded-full after:bg-white after:shadow after:transition-[left] peer-checked:after:left-[23px]"
      />
    </label>
  )
}
