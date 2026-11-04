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
  // アルバムを見せない設定（項目を出さない）を基本にする。見せる設定のテストは、個別に上書きする
  notify_album: null,
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

describe('NotificationSettingsView（アルバム）', () => {
  it('アルバムを見せない設定（null）のときは、アルバムの項目を出さない（FR-017）', () => {
    const shown = text(render())

    expect(shown).not.toContain('アルバム')
    expect(shown).not.toContain('Album')
  })

  it('アルバムを見せる設定のときは、項目を出し、保存した値どおりに選んだ状態で出る', () => {
    const on = render({ settings: { ...settings, notify_album: true } })
    const off = render({ settings: { ...settings, notify_album: false } })

    // アルバムは「記録のまとめに入れるもの」の中に、つまみで並べる（#449）
    expect(text(on)).toContain('アルバムの新しい写真')
    // 返事 + 項目 3 つ + アルバム = チェック 5 つ（オフなら 4 つ）
    expect(on.match(/type="checkbox"[^>]*checked=""/g)).toHaveLength(5)
    expect(off.match(/type="checkbox"[^>]*checked=""/g)).toHaveLength(4)
  })

  it('API がキーごと省略して返したとき（見せない設定。response_model_exclude_none）も、項目を出さない', () => {
    // 実際の API は null ではなく、notify_album のキーを返さない。undefined でも出ないことを確かめる
    const omitted: NotificationSettingsData = {
      notify_reply: true,
      notify_items: ['meal', 'mood', 'sleep'],
      frequency: 'daily',
      email: 'family@example.test',
      available_items: ['meal', 'mood', 'sleep'],
    }

    const html = render({ settings: omitted })

    expect(text(html)).not.toContain('アルバム')
    // 返事 + 項目 3 つ = チェック 4 つ
    expect(html.match(/type="checkbox"[^>]*checked=""/g)).toHaveLength(4)
  })
})

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
      draft: {
        notify_reply: false,
        notify_items: ['meal'],
        frequency: 'weekly',
        notify_album: null,
      },
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

  it('変えたときだけ、下に「変更があります」と「保存する」の帯を出す。保存中は押せず、文言が変わる（#449）', () => {
    const unchanged = render()
    const idle = render({ draft: { ...toDraft(settings), frequency: 'weekly' } })
    const saving = render({ saving: true })

    expect(text(unchanged)).not.toContain('保存する')
    expect(text(idle)).toContain('変更があります')
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
      draft: { notify_reply: true, notify_items: ['meal'], frequency: 'daily', notify_album: null },
    })

    expect(text(changed)).toContain('変更があります')
    expect(text(render())).not.toContain('変更があります')
  })

  it('保存に失敗したときは、エラーの文を出す（選んだ内容は、残る）', () => {
    const html = render({
      errorKey: 'error.server_error',
      draft: { notify_reply: false, notify_items: ['meal'], frequency: 'none', notify_album: null },
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

describe('通知の設定の見た目（#449）', () => {
  it('オン・オフは、つまみ（role="switch"）で読み上げに伝える', () => {
    const html = render()

    // 返事 1 ＋ 項目 4（食事・機嫌・眠り・様子のメモ）
    expect(html.match(/role="switch"/g)).toHaveLength(5)
  })

  it('頻度は、いつ届くかのひとことを添える', () => {
    expect(text(render())).toContain('その日の分をまとめて')
  })

  it('緊急のときは電話で知らせる案内を、いつも出す', () => {
    expect(text(render())).toContain('緊急のときは、施設からお電話します')
  })
})
