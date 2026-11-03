import { describe, expect, it } from 'vitest'
import {
  isChanged,
  selectableItems,
  toDraft,
  toggleItem,
  type NotificationSettingsData,
} from './notificationSettingsView'

const settings: NotificationSettingsData = {
  notify_reply: true,
  notify_items: ['meal', 'mood', 'sleep'],
  frequency: 'daily',
  email: 'family@example.test',
  available_items: ['meal', 'mood', 'sleep', 'memo'],
  notify_album: true,
}

describe('toDraft', () => {
  it('保存した設定から、送る内容だけ（メール・選べる項目は除く）を作る', () => {
    expect(toDraft(settings)).toEqual({
      notify_reply: true,
      notify_items: ['meal', 'mood', 'sleep'],
      frequency: 'daily',
      notify_album: true,
    })
  })

  it('アルバムを見せない設定（notify_album が null）は、null のまま持つ', () => {
    expect(toDraft({ ...settings, notify_album: null }).notify_album).toBeNull()
  })

  it('API がキーごと省略した（見せない設定）ときも、null にそろえる', () => {
    const omitted: NotificationSettingsData = {
      notify_reply: true,
      notify_items: ['meal'],
      frequency: 'daily',
      email: 'family@example.test',
      available_items: ['meal'],
    }

    expect(toDraft(omitted).notify_album).toBeNull()
  })

  it('項目の配列は、元の配列とは別のものにする（選んでいる途中で、元を書き換えない）', () => {
    const draft = toDraft(settings)

    expect(draft.notify_items).not.toBe(settings.notify_items)
  })
})

describe('toggleItem', () => {
  it('選ぶと足し、はずすと除く。並びは meal・mood・sleep の順にそろえる', () => {
    expect(toggleItem(['sleep'], 'meal', true)).toEqual(['meal', 'sleep'])
    expect(toggleItem(['meal', 'mood', 'sleep'], 'mood', false)).toEqual(['meal', 'sleep'])
  })

  it('同じ項目を 2 回選んでも、1 つのまま', () => {
    expect(toggleItem(['meal'], 'meal', true)).toEqual(['meal'])
  })

  it('選択肢に出ていない項目（いま非開示のもの）は、触らずに残す', () => {
    expect(toggleItem(['meal', 'memo'], 'meal', false)).toEqual(['memo'])
    expect(toggleItem(['memo'], 'sleep', true)).toEqual(['sleep', 'memo'])
  })

  it('元の配列は、書き換えない', () => {
    const items = ['meal']

    toggleItem(items, 'mood', true)

    expect(items).toEqual(['meal'])
  })
})

describe('isChanged', () => {
  it('同じ内容なら、変わっていない', () => {
    expect(isChanged(toDraft(settings), toDraft(settings))).toBe(false)
  })

  it('返事・項目・頻度のどれかが違えば、変わっている', () => {
    const saved = toDraft(settings)

    expect(isChanged(saved, { ...saved, notify_reply: false })).toBe(true)
    expect(isChanged(saved, { ...saved, frequency: 'weekly' })).toBe(true)
    expect(isChanged(saved, { ...saved, notify_items: ['meal'] })).toBe(true)
    expect(isChanged(saved, { ...saved, notify_album: false })).toBe(true)
  })
})

describe('selectableItems', () => {
  it('いま選べる項目だけを、meal・mood・sleep の順で返す', () => {
    expect(selectableItems(['sleep', 'meal'])).toEqual(['meal', 'sleep'])
  })

  it('様子のメモ（memo）も選べる。知らない項目は、選択肢に出さない（並びは固定）', () => {
    expect(selectableItems(['memo', 'mood'])).toEqual(['mood', 'memo'])
    expect(selectableItems(['snack', 'mood'])).toEqual(['mood'])
  })

  it('選べる項目がなければ、空', () => {
    expect(selectableItems([])).toEqual([])
  })
})
