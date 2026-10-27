import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { CompleteView } from './SignupComplete'
import { SignupForm } from './Signup'

// ふりがな（<rt>・<rp>）と、そのほかのタグを外した、画面の文字だけ
const textOf = (html: string) =>
  html.replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '').replace(/<[^>]*>/g, '')

const plan = { plan_name: '月額プラン', amount_jpy: 10000 }

const renderForm = (props: Partial<Parameters<typeof SignupForm>[0]> = {}) =>
  renderToStaticMarkup(
    <SignupForm
      plan={plan}
      canceled={false}
      submitting={false}
      errorKey={null}
      onSubmit={() => {}}
      {...props}
    />,
  )

const renderComplete = (props: Parameters<typeof CompleteView>[0]) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <CompleteView {...props} />
    </MemoryRouter>,
  )

describe('SignupForm', () => {
  it('プラン名・月額と、5 つの入力欄を出す', () => {
    const html = renderForm()

    expect(html).toContain('月額プラン')
    expect(html).toContain('10,000')
    for (const name of ['facility_name', 'director_name', 'email', 'email_confirm', 'password']) {
      expect(html).toContain(`name="${name}"`)
    }
    expect(html).toContain('type="password"')
    // パスワードの決まり（半角の英数字と記号で 8〜64 文字）を、入力欄の近くに書く
    expect(html).toContain('8〜64')
  })

  it('押せる状態の申し込みボタンと、押したあとの押せない状態', () => {
    expect(renderForm()).not.toMatch(/<button type="submit" disabled=""/)
    expect(renderForm({ submitting: true })).toMatch(/<button type="submit" disabled=""/)
  })

  it('「戻る」で戻ったときは、完了していないことを伝える', () => {
    expect(textOf(renderForm({ canceled: true }))).toContain('完了していません')
    expect(textOf(renderForm())).not.toContain('完了していません')
  })

  it('申し込めなかった理由を出す', () => {
    expect(renderForm({ errorKey: 'error.email_mismatch' })).toContain('メールアドレスが違います')
  })
})

describe('CompleteView', () => {
  it('アカウントができるまでは、確認中と出す', () => {
    const html = renderComplete({ status: 'confirming' })

    expect(textOf(html)).toContain('確認しています')
    expect(html).not.toContain('/login')
  })

  it('確認に時間がかかっているときは、少し待って読み直すよう案内する', () => {
    const html = renderComplete({ status: 'confirming', timedOut: true })

    expect(textOf(html)).toContain('時間がかかっています')
    expect(textOf(html)).not.toContain('確認しています')
  })

  it('できたら、ログイン用の ID と控える注意、ログイン画面へのボタンを出す', () => {
    const html = renderComplete({ status: 'completed', loginId: 's00001' })

    expect(html).toContain('s00001')
    expect(textOf(html)).toContain('控えてください')
    expect(html).toContain('href="/login"')
  })

  it('ID を出せる時間が過ぎていたら、ID は出さずに案内を出す', () => {
    const html = renderComplete({ status: 'completed' })

    expect(html).not.toContain('data-testid="login-id"')
    expect(textOf(html)).toContain('時間が過ぎました')
    expect(html).toContain('href="/login"')
  })

  it('支払われていないときは、申し込みの画面へ戻れる', () => {
    const html = renderComplete({ status: 'not_completed' })

    expect(textOf(html)).toContain('確認できませんでした')
    expect(html).toContain('href="/signup"')
  })
})
