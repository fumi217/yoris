import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { adminMenuFor } from './adminMenu'
import { warningsFor } from './disclosureRules'
import { DisclosureForm, type Disclosure } from './DisclosureSettings'

const disclosure: Disclosure = {
  items: [
    { code: 'meal', visible: true },
    { code: 'mood', visible: false },
    { code: 'sleep', visible: true },
  ],
  themes: [{ code: 'theme.meals', emoji: '🍚', visible: true }],
  features: [{ code: 'album', visible: true }],
  related: [{ item: 'meal', theme: 'theme.meals' }],
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
    // 事務員が開けるのは、家族からのメッセージ（#88）・利用料のお支払い・面会の設定・予約の一覧（開示設定は出ない）
    expect(adminMenuFor('clerk').map((item) => item.to)).toEqual([
      '/admin/messages',
      '/admin/billing',
      '/admin/visit-settings',
      '/admin/visits',
    ])
    expect(adminMenuFor(null)).toEqual([])
  })
})

describe('DisclosureForm', () => {
  it('機能の欄に、アルバムの行（見せる／見せない）を出す（spec 005 の 005-T023）', () => {
    const html = render()

    expect(html).toContain('name="feature-album"')
    expect(html).toContain('アルバム')
  })

  it('記録の項目とテーマを、今の設定で並べる', () => {
    const html = render()

    expect(html).toContain('食事')
    expect(html).toContain('name="theme-theme.meals"')
    expect(html).toContain('🍚')
    // 見せる：食事・眠り・テーマ・アルバム、見せない：機嫌（行ごとに 1 つ選ばれている）
    expect(html.match(/type="radio"[^>]*checked=""/g)).toHaveLength(5)
  })

  it('何も変えていなければ、保存のボタンは押せない', () => {
    expect(render()).toMatch(/<button type="submit" disabled=""/)
  })

  it('保存できなかったら、理由を出す', () => {
    expect(render({ errorKey: 'error.forbidden' })).toContain('できません')
  })
})

describe('warningsFor', () => {
  const related = [
    { item: 'mood', theme: 'theme.enjoying' },
    { item: 'meal', theme: 'theme.meals' },
  ]

  it('記録の項目は見せないのに、組のテーマを見せるときだけ注意書きを出す', () => {
    const visible: Record<string, boolean> = {
      'items:mood': false,
      'themes:theme.enjoying': true,
      'items:meal': false,
      'themes:theme.meals': false,
    }
    const warnings = warningsFor(related, (kind, code) => visible[`${kind}:${code}`])

    expect(warnings).toEqual([{ item: 'mood', theme: 'theme.enjoying' }])
  })
})

describe('DisclosureForm の注意書き', () => {
  it('保存した設定で当てはまる組に、注意書きを出す', () => {
    const html = render({
      disclosure: { ...disclosure, items: [{ code: 'meal', visible: false }] },
    })

    expect(html).toContain('⚠️')
    expect(html).toContain('このままでも')
  })

  it('当てはまる組がなければ、出さない', () => {
    expect(render()).not.toContain('⚠️')
  })
})
