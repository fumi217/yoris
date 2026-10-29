import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import ja from '../../i18n/ja.json'
import { adminMenuFor } from './adminMenu'
import { ChangeRulesView, type ChangeRule, type ChangeRuleHistoryRow } from './ChangeRules'
import { visibleSaved } from './savedRule'

const rules: ChangeRule[] = [
  { code: 'meal_low', enabled: true },
  { code: 'mood_low', enabled: false },
  { code: 'sleep_poor', enabled: true },
]
const history: ChangeRuleHistoryRow[] = [
  {
    id: 2,
    rule_code: 'mood_low',
    enabled_before: true,
    enabled_after: false,
    changed_by_name: '架空 施設長',
    changed_at: '2026-10-28T01:30:00Z',
  },
]

const render = (props: Partial<Parameters<typeof ChangeRulesView>[0]> = {}) =>
  renderToStaticMarkup(
    <ChangeRulesView
      rules={rules}
      history={history}
      savingCode={null}
      saved={null}
      errorKey={null}
      onChange={() => {}}
      {...props}
    />,
  )

/** 辞書の値から、ふりがなの書き方 `{漢字|かんじ}` の中を取り除いて、漢字が残っているかを調べる。 */
function bareKanji(text: string): string[] {
  return text.replace(/\{[^|}]*\|[^}]*\}/g, '').match(/[一-鿿々]/g) ?? []
}

describe('adminMenu', () => {
  it('変化の目印の設定は、生活相談員・施設長にだけ出す', () => {
    expect(adminMenuFor('counselor').map((item) => item.to)).toContain('/admin/change-rules')
    expect(adminMenuFor('director').map((item) => item.to)).toContain('/admin/change-rules')
    expect(adminMenuFor('clerk').map((item) => item.to)).not.toContain('/admin/change-rules')
  })
})

describe('ChangeRulesView', () => {
  it('決まり 3 つを、今のオン／オフで並べる', () => {
    const html = render()

    expect(html).toContain('name="rule-meal_low"')
    expect(html).toContain('name="rule-mood_low"')
    expect(html).toContain('name="rule-sleep_poor"')
    // 行ごとに 1 つ選ばれている（オン：食事量・眠り、オフ：機嫌）
    expect(html.match(/type="radio"[^>]*checked=""/g)).toHaveLength(3)
    expect(html).toContain('食事量')
  })

  it('オフにすると目印が消えることを、画面に書く', () => {
    expect(render()).toContain('オフにすると')
  })

  it('履歴を、いつ・誰が・どの決まりを・どう変えたかで出す', () => {
    const html = render()

    expect(html).toContain('架空 施設長')
    // 日本時間（UTC+9）の 10 月 28 日 10:30
    expect(html).toContain('10:30')
    expect(html).toContain('オフ')
    // 「…を「オフ」にしました」と、したことが分かる文にする
    expect(html).toContain('にしました')
  })

  it('履歴がなければ、そのことを出す', () => {
    expect(render({ history: [] })).toContain('まだ')
  })

  it('履歴を読めないときは、履歴の欄だけ出さない', () => {
    const html = render({ history: null })

    expect(html).not.toContain('履歴')
    expect(html).toContain('name="rule-meal_low"')
  })

  it('保存できたら、どの決まりを、オンとオフのどちらにしたかを出す', () => {
    // 状態の欄（role="status"）だけを見る。決まりの一覧にも同じ名前が出るため
    const status = (props: Parameters<typeof render>[0]) =>
      render(props).match(/<p role="status"[^>]*>(.*?)<\/p>/)?.[1] ?? ''

    const off = status({ saved: { code: 'mood_low', enabled: false } })
    expect(off).toContain('<rt>きげん</rt>')
    expect(off).toContain('オフにしました')
    const on = status({ saved: { code: 'meal_low', enabled: true } })
    expect(on).toContain('オンにしました')
  })

  it('辞書にない決まりのコードは、コードのまま出す（辞書のキーを出さない）', () => {
    const html = render({
      rules: [{ code: 'new_rule', enabled: true }],
      history: [{ ...history[0], rule_code: 'new_rule' }],
    })

    expect(html).toContain('new_rule')
    expect(html).not.toContain('admin.change_rules')
  })

  it('保存できなかったら、理由を出す', () => {
    const html = render({ errorKey: 'error.forbidden' })

    // 漢字にふりがなが付く（「{表示|ひょうじ}」が <ruby> で分かれる）ので、読みと続きの文字で確かめる
    expect(html).toContain('<rt>ひょうじ</rt>')
    expect(html).toContain('できません')
  })

  it('保存中は、押しても受け付けないが、`disabled` にはしない（キーボードのフォーカスが外れないように）', () => {
    const html = render({ savingCode: 'meal_low' })

    // 3 つの決まりのラジオ（オン 3 つ＋オフにしている決まりのオフ 1 つ）がすべて aria-disabled
    expect(html.match(/aria-disabled="true"/g)).toHaveLength(4)
    // ラジオは `disabled` にしない。2 回押すボタン（オンの決まりの「オフ」2 つ）だけが押せない
    expect(html.match(/disabled=""/g)).toHaveLength(2)
    expect(html).not.toMatch(/type="radio"[^>]*disabled=""/)
    expect(html).toContain('<rt>ほぞん</rt>')
    expect(html).toContain('しています')
  })

  it('決まりごとに、名前でグループにする（読み上げで、どの決まりのボタンかが伝わる）', () => {
    const html = render()

    for (const code of ['meal_low', 'mood_low', 'sleep_poor']) {
      expect(html).toContain(`id="rule-name-${code}"`)
      expect(html).toContain(`role="group" aria-labelledby="rule-name-${code}"`)
    }
  })

  it('オンの決まりをオフにするボタンは、2 回押して決める（確かめ済みの目印も消えるため）', () => {
    const html = render()

    // オンの決まり（食事量・眠り）：オンのラジオと、オフにするボタン（ラジオではない）
    expect(html.match(/<button[^>]*type="button"/g)).toHaveLength(2)
    // オフの決まり（機嫌）：オンとオフの 2 つのラジオ。ほかの 2 つはオンのラジオだけ
    expect(html.match(/type="radio"/g)).toHaveLength(4)
  })

  it('選ばれている側は、色だけでなく太字でも示す。✔ は付けない（幅が変わって位置がずれるため）', () => {
    const html = render()

    expect(html.match(/font-bold text-white/g)).toHaveLength(3)
    expect(html).not.toContain('✔')
  })

  it('オンとオフは同じ幅にする（行ごとに位置がずれないように）', () => {
    expect(render().match(/min-w-20/g)?.length).toBeGreaterThanOrEqual(5)
  })
})

describe('visibleSaved', () => {
  it('いまの値と同じなら、保存の文を出す', () => {
    expect(visibleSaved(rules, { code: 'mood_low', enabled: false })).toEqual({
      code: 'mood_low',
      enabled: false,
    })
  })

  it('ほかの人が変えて、いまの値と食い違ったら、出さない', () => {
    expect(visibleSaved(rules, { code: 'mood_low', enabled: true })).toBeNull()
  })

  it('保存の結果がなければ、出さない。知らない決まりも出さない', () => {
    expect(visibleSaved(rules, null)).toBeNull()
    expect(visibleSaved(rules, { code: 'new_rule', enabled: true })).toBeNull()
  })
})

describe('辞書（admin.change_rules）', () => {
  it('すべての漢字にふりがなが付いている（SC-011。職員の画面）', () => {
    const texts: string[] = []
    const collect = (node: unknown) => {
      if (typeof node === 'string') texts.push(node)
      else if (node && typeof node === 'object') Object.values(node).forEach(collect)
    }
    collect(ja.admin.change_rules)
    collect(ja.admin.menu.change_rules)

    expect(texts.flatMap(bareKanji)).toEqual([])
  })
})
