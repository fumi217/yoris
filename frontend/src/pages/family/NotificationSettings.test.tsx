import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { NotificationSettingsView } from './NotificationSettings'
import {
  toDraft,
  type NotificationSettingsData,
  type SettingsDraft,
} from './notificationSettingsView'

const settings: NotificationSettingsData = {
  notify_reply: true,
  notify_items: ['meal', 'mood', 'sleep'],
  frequency: 'daily',
  email: 'family@example.test',
  available_items: ['meal', 'mood', 'sleep', 'memo'],
}

type Extra = {
  settings?: NotificationSettingsData
  draft?: SettingsDraft
  saving?: boolean
  saved?: boolean
  errorKey?: string | null
}

const render = (extra: Extra = {}) => {
  const shown = extra.settings ?? settings
  return renderToStaticMarkup(
    <NotificationSettingsView
      settings={shown}
      draft={extra.draft ?? toDraft(shown)}
      saving={extra.saving ?? false}
      saved={extra.saved ?? false}
      errorKey={extra.errorKey ?? null}
      onChange={() => {}}
      onSave={() => {}}
    />,
  )
}

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('NotificationSettingsView', () => {
  it('緊急のときは電話で知らせる、という案内を、いつも出す（FR-028）', () => {
    expect(text(render())).toContain('緊急のときは、施設からお電話します')
  })

  it('保存した設定どおりに、選んだ状態で出る（返事・3 つの項目・頻度）', () => {
    const html = render()

    // 返事 + 項目 3 つ = チェック 4 つ。頻度は、3 つのうち 1 つ
    expect(html.match(/type="checkbox"[^>]*checked=""/g)).toHaveLength(4)
    expect(html.match(/type="radio"/g)).toHaveLength(3)
    expect(html.match(/type="radio"[^>]*checked=""/g)).toHaveLength(1)
  })

  it('選んでいる途中の内容（保存前）が、そのまま出る', () => {
    const html = render({
      draft: { notify_reply: false, notify_items: ['meal'], frequency: 'weekly' },
    })

    expect(html.match(/type="checkbox"[^>]*checked=""/g)).toHaveLength(1)
    expect(html).toMatch(/type="radio"[^>]*checked=""/)
  })

  it('非開示の項目は、選択肢に出さない', () => {
    const html = render({ settings: { ...settings, available_items: ['meal', 'sleep'] } })

    // 返事 + 食事 + 眠り = チェック 3 つ。機嫌は出ない
    expect(html.match(/type="checkbox"/g)).toHaveLength(3)
    expect(text(html)).not.toContain('機嫌')
  })

  it('選べる項目が 1 つもないときは、その案内を出す', () => {
    const html = render({ settings: { ...settings, available_items: [] } })

    expect(text(html)).toContain('いま選べる項目はありません')
    expect(html.match(/type="checkbox"/g)).toHaveLength(1) // 返事だけ
  })

  it('送り先のメールアドレスと、届かないときの案内を出す', () => {
    const shown = text(render())

    expect(shown).toContain('family@example.test')
    expect(shown).toContain('迷惑メール')
  })

  it('「保存する」ボタンを出す。保存中は押せず、文言が変わる', () => {
    const idle = render()
    const saving = render({ saving: true })

    expect(text(idle)).toContain('保存する')
    expect(idle).not.toMatch(/<button[^>]*disabled=""/)
    expect(text(saving)).toContain('保存しています')
    expect(saving).toMatch(/<button[^>]*disabled=""/)
  })

  it('保存したら「保存しました」を出す（読み上げにも伝わる場所に）', () => {
    const html = render({ saved: true })

    expect(html).toMatch(/role="status"[^>]*>.*保存/s)
    expect(text(html)).toContain('保存しました')
    expect(text(render())).not.toContain('保存しました')
  })

  it('保存していない変更があるときだけ、「保存する」を押す案内を出す', () => {
    const changed = render({
      draft: { notify_reply: true, notify_items: ['meal'], frequency: 'daily' },
    })

    expect(text(changed)).toContain('変更があります')
    expect(text(render())).not.toContain('変更があります')
  })

  it('保存に失敗したときは、エラーの文を出す（選んだ内容は、残る）', () => {
    const html = render({
      errorKey: 'error.server_error',
      draft: { notify_reply: false, notify_items: ['meal'], frequency: 'none' },
    })

    expect(html).toContain('role="alert"')
    expect(html.match(/type="checkbox"[^>]*checked=""/g)).toHaveLength(1)
  })

  it('メールアドレスは、文字としてだけ出す（HTML として解釈しない）', () => {
    const html = render({ settings: { ...settings, email: '<b>x</b>@example.test' } })

    expect(html).not.toContain('<b>x</b>')
    expect(html).toContain('&lt;b&gt;x&lt;/b&gt;@example.test')
  })
})
