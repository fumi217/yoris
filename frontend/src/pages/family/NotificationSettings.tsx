import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, messageKeyOf } from '../../api/client'
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
    <NotificationSettingsView
      settings={settings}
      draft={draft}
      saving={save.isPending}
      saved={saved}
      errorKey={save.isError ? messageKeyOf(save.error) : null}
      onChange={change}
      onSave={() => save.mutate(draft)}
    />
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

const optionClass = 'flex min-h-12 cursor-pointer items-center gap-3 rounded border-2 px-3'

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

  return (
    <section className="space-y-6 p-4">
      <h1 className="text-xl font-bold">
        <Text k="notification_settings.title" />
      </h1>
      {/* 緊急の連絡は、メールやお知らせではなく、電話で行う（FR-028）。いつも出す */}
      <p className="rounded border-2 border-amber-600 bg-amber-50 p-2 font-bold">
        <Text k="contact_book.emergency" />
      </p>
      <p className="text-gray-700">
        <Text k="notification_settings.intro" />
      </p>

      <fieldset className="space-y-2">
        <legend className="mb-1 font-bold">
          <Text k="notification_settings.reply_title" />
        </legend>
        <label
          className={`${optionClass} ${draft.notify_reply ? 'border-primary' : 'border-field-line'}`}
        >
          <input
            type="checkbox"
            className="h-5 w-5"
            checked={draft.notify_reply}
            onChange={(event) => onChange({ ...draft, notify_reply: event.target.checked })}
          />
          <Text k="notification_settings.reply_label" />
        </label>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="mb-1 font-bold">
          <Text k="notification_settings.items_title" />
        </legend>
        <p className="text-sm text-gray-600">
          <Text k="notification_settings.items_hint" />
        </p>
        {items.length === 0 ? (
          <p className="text-gray-600">
            <Text k="notification_settings.items_empty" />
          </p>
        ) : (
          items.map((item) => {
            const checked = draft.notify_items.includes(item)
            return (
              <label
                key={item}
                className={`${optionClass} ${checked ? 'border-primary' : 'border-field-line'}`}
              >
                <input
                  type="checkbox"
                  className="h-5 w-5"
                  checked={checked}
                  onChange={(event) =>
                    onChange({
                      ...draft,
                      notify_items: toggleItem(draft.notify_items, item, event.target.checked),
                    })
                  }
                />
                <Text k={`notification_settings.item.${item}`} />
              </label>
            )
          })
        )}
      </fieldset>

      {/* アルバムを見せない設定のとき（API がキーを省略して返す。draft では null）は、項目を出さない */}
      {typeof draft.notify_album === 'boolean' && (
        <fieldset className="space-y-2">
          <legend className="mb-1 font-bold">
            <Text k="notification_settings.album_title" />
          </legend>
          <label
            className={`${optionClass} ${draft.notify_album ? 'border-primary' : 'border-field-line'}`}
          >
            <input
              type="checkbox"
              className="h-5 w-5"
              checked={draft.notify_album}
              onChange={(event) => onChange({ ...draft, notify_album: event.target.checked })}
            />
            <Text k="notification_settings.album_label" />
          </label>
        </fieldset>
      )}

      <fieldset className="space-y-2">
        <legend className="mb-1 font-bold">
          <Text k="notification_settings.frequency_title" />
        </legend>
        {FREQUENCIES.map((frequency) => (
          <label
            key={frequency}
            className={`${optionClass} ${
              draft.frequency === frequency ? 'border-primary' : 'border-field-line'
            }`}
          >
            <input
              type="radio"
              name="frequency"
              className="h-5 w-5"
              checked={draft.frequency === frequency}
              onChange={() => onChange({ ...draft, frequency })}
            />
            <Text k={`notification_settings.frequency.${frequency}`} />
          </label>
        ))}
      </fieldset>

      <div className="space-y-1">
        <h2 className="font-bold">
          <Text k="notification_settings.email_title" />
        </h2>
        {/* 送り先のメールアドレス。画面の文字として、そのまま出す（辞書を通さない） */}
        <p className="break-all">{settings.email}</p>
        <p className="text-sm text-gray-600">
          <Text k="notification_settings.email_hint" />
        </p>
      </div>

      <div className="space-y-2">
        {changed && !saving && (
          <p className="text-sm text-gray-700">
            <Text k="notification_settings.changed" />
          </p>
        )}
        <button
          type="button"
          className="min-h-12 w-full rounded bg-primary px-4 font-bold text-white disabled:bg-gray-300"
          disabled={saving}
          onClick={onSave}
        >
          <Text k={saving ? 'notification_settings.saving' : 'notification_settings.save'} />
        </button>
        <p role="status" className="font-bold">
          {saved && <Text k="notification_settings.saved" />}
        </p>
        {errorKey && (
          <p role="alert" className="text-red-800">
            <Text k={errorKey} />
          </p>
        )}
      </div>
    </section>
  )
}
