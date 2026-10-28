import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { DisclosureHistoryView } from './DisclosureHistory'
import { changedAtParts, targetLabelKey, type DisclosureHistoryRow } from './historyRows'

const row = (overrides: Partial<DisclosureHistoryRow> = {}): DisclosureHistoryRow => ({
  id: 1,
  target_type: 'item',
  target_code: 'mood',
  old_visible: true,
  new_visible: false,
  changed_by_name: '猪熊',
  changed_at: '2026-10-26T05:05:00Z', // 日本時間の 14:05
  ...overrides,
})

describe('disclosureHistory', () => {
  it('変えた日時は日本時間で出す', () => {
    expect(changedAtParts('2026-10-26T15:30:00Z')).toEqual({ month: 10, day: 27, time: '00:30' })
  })

  it('記録の項目とテーマで、名前の辞書のキーを分ける', () => {
    expect(targetLabelKey(row())).toBe('disclosure.item.mood')
    expect(targetLabelKey(row({ target_type: 'theme', target_code: 'theme.meals' }))).toBe(
      'theme.meals',
    )
    // 機能（アルバム。spec 005 の 005-T023）
    expect(targetLabelKey(row({ target_type: 'feature', target_code: 'album' }))).toBe(
      'disclosure.feature.album',
    )
  })
})

describe('DisclosureHistoryView', () => {
  it('いつ・誰が・何を、を出す', () => {
    const html = renderToStaticMarkup(<DisclosureHistoryView rows={[row()]} />)

    expect(html).toContain('14:05')
    expect(html).toContain('猪熊')
    expect(html).toContain('<ruby>機嫌')
    // 「見せない」にした
    expect(html).toContain('せない')
  })

  it('職員の名前は、HTML として解釈しない', () => {
    const html = renderToStaticMarkup(
      <DisclosureHistoryView rows={[row({ changed_by_name: '<b>x</b>' })]} />,
    )

    expect(html).not.toContain('<b>x</b>')
  })

  it('変更がなければ、そう伝える', () => {
    expect(renderToStaticMarkup(<DisclosureHistoryView rows={[]} />)).toContain('ありません')
  })
})
