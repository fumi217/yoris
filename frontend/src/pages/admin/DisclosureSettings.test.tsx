import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { adminMenuFor } from './adminMenu'
import { DisclosureForm, type Disclosure } from './DisclosureSettings'

const disclosure: Disclosure = {
  items: [
    { code: 'meal', visible: true },
    { code: 'mood', visible: false },
    { code: 'sleep', visible: true },
  ],
  themes: [{ code: 'theme.meals', emoji: '🍚', visible: true }],
}

const render = (props: Partial<Parameters<typeof DisclosureForm>[0]> = {}) =>
  renderToStaticMarkup(
    <DisclosureForm
      disclosure={disclosure}
      saving={false}
      saved={false}
      errorKey={null}
      onSave={() => {}}
      {...props}
    />,
  )

describe('adminMenu', () => {
  it('開示設定は、生活相談員・施設長にだけ出す', () => {
    expect(adminMenuFor('counselor').map((item) => item.to)).toContain('/admin/disclosure')
    expect(adminMenuFor('director').map((item) => item.to)).toContain('/admin/disclosure')
    expect(adminMenuFor('clerk')).toEqual([])
    expect(adminMenuFor(null)).toEqual([])
  })
})

describe('DisclosureForm', () => {
  it('記録の項目とテーマを、今の設定で並べる', () => {
    const html = render()

    expect(html).toContain('食事')
    expect(html).toContain('name="theme-theme.meals"')
    expect(html).toContain('🍚')
    // 見せる：食事・眠り・テーマ、見せない：機嫌
    expect(html.match(/type="radio"[^>]*checked=""/g)).toHaveLength(4)
  })

  it('何も変えていなければ、保存のボタンは押せない', () => {
    expect(render()).toMatch(/<button type="submit" disabled=""/)
  })

  it('保存できなかったら、理由を出す', () => {
    expect(render({ errorKey: 'error.forbidden' })).toContain('表示できません')
  })
})
