import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { adminMenuFor } from './adminMenu'
import { CreatedView, StaffFormView } from './StaffAccounts'
import {
  DISPLAY_NAME_MAX,
  nameProblem,
  OCCUPATIONS,
  ROLES,
  toBody,
  type CreatedStaff,
} from './staffAccountRules'

const renderForm = (props: Partial<Parameters<typeof StaffFormView>[0]> = {}) =>
  renderToStaticMarkup(
    <StaffFormView saving={false} errorKey={null} onSubmit={() => {}} {...props} />,
  )

// ふりがな（<rt>）と、タグを外した文字だけ（漢字にふりがなが付いていても、文言で確かめられる）
const plain = (html: string) => html.replace(/<r[tp]>.*?<\/r[tp]>/g, '').replace(/<[^>]+>/g, '')

const created: CreatedStaff = {
  id: 17,
  login_id: 's00017',
  display_name: '新人',
  role: 'care_worker',
  occupation: 'nurse',
  initial_password: 'kM7xQ2pA',
}

describe('表示名の確かめ', () => {
  it('前後の空白を除いて 1〜20 文字なら問題なし', () => {
    expect(nameProblem('田中')).toBeNull()
    expect(nameProblem('  田中  ')).toBeNull()
    expect(nameProblem('あ'.repeat(DISPLAY_NAME_MAX))).toBeNull()
  })

  it('空・空白だけは empty、21 文字は too_long', () => {
    expect(nameProblem('')).toBe('empty')
    expect(nameProblem('   ')).toBe('empty')
    expect(nameProblem('あ'.repeat(DISPLAY_NAME_MAX + 1))).toBe('too_long')
  })

  it('絵文字も 1 文字と数える', () => {
    expect(nameProblem('😀'.repeat(DISPLAY_NAME_MAX))).toBeNull()
  })
})

describe('送る中身', () => {
  it('表示名の前後の空白を除き、職種を選ばなければ null にする', () => {
    expect(toBody('  新人 ', 'leader', '')).toEqual({
      display_name: '新人',
      role: 'leader',
      occupation: null,
    })
  })

  it('職種を選んだらそのコードを送る', () => {
    expect(toBody('新人', 'care_worker', 'nurse').occupation).toBe('nurse')
  })

  it('選べる役割は 5 つ、職種は 8 つで、役割の 5 つは職種にも入っている', () => {
    expect(ROLES).toHaveLength(5)
    expect(OCCUPATIONS).toHaveLength(8)
    for (const role of ROLES) expect(OCCUPATIONS).toContain(role)
  })
})

describe('フォーム', () => {
  it('表示名・役割・職種の欄と、作るボタンが出る', () => {
    const html = renderForm()

    expect(html).toContain('id="staff-display-name"')
    expect(html).toContain('id="staff-role"')
    expect(html).toContain('id="staff-occupation"')
    expect(plain(html)).toContain('職員のアカウントを作る')
  })

  it('役割は 5 つ、職種は「選択しない」＋ 8 つを選べる', () => {
    const html = renderForm()
    const roleSelect = html.split('id="staff-role"')[1].split('</select>')[0]
    const occupationSelect = html.split('id="staff-occupation"')[1].split('</select>')[0]

    expect(roleSelect.match(/<option/g)).toHaveLength(5)
    expect(occupationSelect.match(/<option/g)).toHaveLength(9)
    expect(occupationSelect).toContain('看護師')
    expect(occupationSelect).toContain('ケアマネジャー')
    expect(occupationSelect).toContain('選択しない')
    // 看護師などは、役割には出さない（役割は介護職員を選ぶ）
    expect(roleSelect).not.toContain('看護師')
  })

  it('項目名は「職員名」で、職員名・役割は※必須、職種は※任意', () => {
    const text = plain(renderForm())

    expect(text).toContain('職員名')
    expect(text).not.toContain('表示名')
    expect(text.match(/※必須/g)).toHaveLength(2)
    expect(text.match(/※任意/g)).toHaveLength(1)
    expect(text.indexOf('職種※任意')).toBeGreaterThan(-1)
  })

  it('最初の役割は介護職員で、職種は選択しない状態', () => {
    const html = renderForm()

    expect(html).toMatch(/<option value="care_worker" selected/)
    expect(html).toMatch(/<option value="" selected/)
  })

  it('押す前は、入力の間違いの文言を出さない', () => {
    expect(renderForm()).not.toContain('role="alert"')
  })

  it('API のエラーは、辞書の文言で出す', () => {
    expect(plain(renderForm({ errorKey: 'error.forbidden' }))).toContain(
      'このページは表示できません',
    )
  })

  it('作っている間は、ボタンを押せず「作成しています」と出す', () => {
    const html = renderForm({ saving: true })

    expect(plain(html)).toContain('作成しています')
    expect(html).toMatch(/<button[^>]*disabled/)
  })

  it('パスワードの入力欄はない（初期パスワードは自動で作る）', () => {
    expect(renderForm()).not.toContain('type="password"')
  })
})

describe('作ったあとの表示', () => {
  it('ID と初期パスワードを出し、閉じる前にコピーするよう伝える', () => {
    const html = renderToStaticMarkup(<CreatedView created={created} onClose={() => {}} />)

    expect(html).toContain('s00017')
    expect(html).toContain('kM7xQ2pA')
    // 作った職員の名前は、項目名「職員名」のとなりに出す
    expect(plain(html)).toContain('職員名新人')
    expect(plain(html)).toContain('画面を閉じる前に')
    expect(plain(html)).toContain('コピーしてください')
    expect(plain(html)).toContain('コピーする')
  })

  it('入力欄は出さない（パスワードを入れ直す画面ではない）', () => {
    const html = renderToStaticMarkup(<CreatedView created={created} onClose={() => {}} />)

    expect(html).not.toContain('<input')
  })
})

describe('管理画面のメニュー', () => {
  it('生活相談員・施設長だけに出す', () => {
    const has = (role: Parameters<typeof adminMenuFor>[0]) =>
      adminMenuFor(role).some((item) => item.to === '/admin/staff-accounts')

    expect(has('counselor')).toBe(true)
    expect(has('director')).toBe(true)
    expect(has('clerk')).toBe(false)
    expect(has('care_worker')).toBe(false)
    expect(has('leader')).toBe(false)
  })
})
