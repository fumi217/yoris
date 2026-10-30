// 家族の通知設定の画面の、型と小さな関数（spec 001 の 001-T064・FR-023）。
// 画面から分けてあるのは、項目の切り替え・変更の有無を、テストしやすくするため。

/** まとめを送る頻度（API の frequency と同じ）。 */
export const FREQUENCIES = ['daily', 'weekly', 'none'] as const

/** 通知に選べる記録項目（API の notify_items と同じ。並びもこの順）。 */
export const ITEM_CODES = ['meal', 'mood', 'sleep'] as const

/** GET・PUT /api/family/notification-settings の返り値。 */
export type NotificationSettingsData = {
  notify_reply: boolean
  notify_items: string[]
  frequency: string
  // 送り先のメールアドレス（ログイン用と同じ）
  email: string
  // いま選べる記録項目（開示されているものだけ）
  available_items: string[]
}

/** 画面で選んでいる途中の内容（PUT で送るもの）。 */
export type SettingsDraft = Pick<
  NotificationSettingsData,
  'notify_reply' | 'notify_items' | 'frequency'
>

/** 保存した設定から、選んでいる途中の内容を作る（email などは含めない）。 */
export function toDraft(settings: NotificationSettingsData): SettingsDraft {
  return {
    notify_reply: settings.notify_reply,
    notify_items: [...settings.notify_items],
    frequency: settings.frequency,
  }
}

/**
 * 記録項目の選択を、1 つ切り替える。並びは ITEM_CODES の順にそろえる。
 * 選択肢に出ていない項目（いま非開示のもの）は、触らずに残す。
 */
export function toggleItem(items: string[], item: string, checked: boolean): string[] {
  const next = new Set(items)
  if (checked) next.add(item)
  else next.delete(item)
  const known = ITEM_CODES.filter((code) => next.has(code))
  const others = [...next].filter((code) => !(ITEM_CODES as readonly string[]).includes(code))
  return [...known, ...others]
}

/** 保存した内容から、変わっているか（「保存してください」の案内に使う）。 */
export function isChanged(saved: SettingsDraft, draft: SettingsDraft): boolean {
  return (
    saved.notify_reply !== draft.notify_reply ||
    saved.frequency !== draft.frequency ||
    saved.notify_items.join(',') !== draft.notify_items.join(',')
  )
}

/** 選択肢に出す項目（いま選べるもののうち、知っている項目だけを、ITEM_CODES の順で）。 */
export function selectableItems(available: string[]): string[] {
  return ITEM_CODES.filter((code) => available.includes(code))
}
