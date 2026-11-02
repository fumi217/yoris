import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { CompleteView } from './SignupComplete'
import { SignupForm } from './Signup'

// ふりがな（<rt>・<rp>）と、そのほかのタグを外した、画面の文字だけ
const textOf = (html: string) =>
  html.replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '').replace(/<[^>]*>/g, '')

const plan = { plan_name: 'システム利用料', amount_jpy: 10000 }

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

    expect(html).toContain('システム利用料')
    expect(html).toContain('10,000')
    for (const name of ['facility_name', 'director_name', 'email', 'email_confirm', 'password']) {
      expect(html).toContain(`name="${name}"`)
    }
    expect(html).toContain('type="password"')
    // パスワードの決まり（半角の英数字と記号で 8〜64 文字）を、入力欄の近くに書く
    expect(html).toContain('8〜64')
  })

  it('5 つの入力欄すべてに、項目名の横に「※必須」を付ける', () => {
    const html = renderForm()

    expect(textOf(html).match(/※必須/g)).toHaveLength(5)
    expect(html.match(/<input[^>]*required=""/g)).toHaveLength(5)
  })

  it('並びは、項目名 → ヒント → 入力欄（デジタル庁の入力欄の並び）', () => {
    const html = renderForm()
    const label =
      html.match(
        /<label[^>]*>(?:(?!<\/label>).)*name="password"(?:(?!<\/label>).)*<\/label>/s,
      )?.[0] ?? ''

    expect(label.indexOf('パスワード')).toBeLessThan(label.indexOf('id="password-hint"'))
    expect(label.indexOf('id="password-hint"')).toBeLessThan(label.indexOf('<input'))
  })

  it('先頭の文は、ボタンの文言と同じ言葉で、次にすることを伝える', () => {
    const text = textOf(renderForm())

    expect(text).toContain('必要な項目を入力して、「お支払いの画面へ進む」を押してください。')
    // ボタンの文言が変わったら、先頭の文も直す
    expect(text.match(/お支払いの画面へ進む/g)).toHaveLength(2)
  })

  it('ヒントは、お名前の例とパスワードの決まりだけ。Stripe の説明は出さない', () => {
    const html = renderForm()

    expect(html.match(/id="[a-z_]+-hint"/g)).toHaveLength(2)
    expect(textOf(html)).toContain('例：山田 太郎')
    // 「今、新しく決めるもの」と分かる言い方で、決まりを伝える
    expect(textOf(html)).toContain('新しいパスワードを決めてください。')
    expect(textOf(html)).toContain('半角の英数字と記号で、8〜64文字で入力してください。')
    expect(textOf(html)).not.toContain('Stripe')
  })

  it('押せる状態の申し込みボタンと、押したあとの押せない状態', () => {
    expect(renderForm()).not.toMatch(/<button type="submit" disabled=""/)
    expect(renderForm({ submitting: true })).toMatch(/<button type="submit" disabled=""/)
  })

  it('「戻る」で戻ったときは、完了していないことを伝える', () => {
    expect(textOf(renderForm({ canceled: true }))).toContain('完了していません')
    expect(textOf(renderForm())).not.toContain('完了していません')
  })

  it('メールアドレスが違うときは、確認用の欄を赤くして、その欄のすぐ下に出す', () => {
    const html = renderForm({ errorKey: 'error.email_mismatch' })

    // 確認用の欄（label）の中に、エラーがある
    const label = html.match(
      /<label[^>]*>(?:(?!<\/label>).)*name="email_confirm"(?:(?!<\/label>).)*<\/label>/s,
    )?.[0]
    expect(label).toBeDefined()
    expect(label).toContain('aria-invalid="true"')
    expect(label).toContain('border-red-700')
    // 文頭は全角の「＊」（デジタル庁のエラーテキストの決まり）
    expect(textOf(label ?? '')).toContain('＊2 回入力したメールアドレスが違います')
    // ほかの欄は赤くしない
    expect(html.match(/aria-invalid="true"/g)).toHaveLength(1)
  })

  it('サーバーが入力を断ったときは、パスワードの欄のすぐ下に出す', () => {
    const html = renderForm({ errorKey: 'error.validation_error' })
    const label = html.match(
      /<label[^>]*>(?:(?!<\/label>).)*name="password"(?:(?!<\/label>).)*<\/label>/s,
    )?.[0]

    expect(textOf(label ?? '')).toContain('推測されやすいため、使えません')
    expect(label).toContain('aria-describedby="password-error password-hint"')
  })

  it('欄が決まらないエラーは、ボタンの上に出す（欄は赤くしない）', () => {
    const html = renderForm({ errorKey: 'error.payment_service_unavailable' })

    expect(textOf(html)).toContain('お支払いの画面を開けませんでした')
    expect(html).not.toContain('aria-invalid')
  })
})

describe('CompleteView', () => {
  it('アカウントができるまでは、確認中と出す', () => {
    const html = renderComplete({ status: 'confirming' })

    expect(textOf(html)).toContain('確認しています')
    expect(html).not.toContain('/login')
  })

  it('確認に時間がかかっているときは、「もう一度確認する」ボタンを出す', () => {
    const html = renderComplete({ status: 'confirming', timedOut: true })

    expect(textOf(html)).toContain('時間がかかっています')
    expect(textOf(html)).toContain('もう一度確認する')
    expect(textOf(html)).not.toContain('このまま少しお待ちください')
  })

  it('時間内は、確認中と出すだけで、ボタンは出さない', () => {
    const html = renderComplete({ status: 'confirming' })

    expect(html).not.toContain('<button')
  })

  it('できたら、ログイン用の ID と控える注意、ログイン画面へのボタンを出す', () => {
    const html = renderComplete({ status: 'completed', loginId: 's00001' })

    expect(html).toContain('s00001')
    expect(textOf(html)).toContain('必ずお控えください')
    expect(textOf(html)).toContain('お申し込み画面で入力いただいたパスワードを使います')
    expect(html).toContain('href="/login"')
  })

  it('ブラウザがコピーに対応していれば、ID の下にコピーのボタンを出す', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <CompleteView status="completed" loginId="s00001" canCopy />
      </MemoryRouter>,
    )

    // 文言は Text の <span> の中（#196）
    expect(html).toMatch(/<button type="button"[^>]*><span>IDをコピーする<\/span><\/button>/)
    // 押すまでは、「コピーしました」は出さない
    expect(textOf(html)).not.toContain('コピーしました')
  })

  it('コピーに対応していなければ、ボタンを出さない（ID は選んでコピーできる）', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <CompleteView status="completed" loginId="s00001" canCopy={false} />
      </MemoryRouter>,
    )

    expect(html).not.toContain('IDをコピーする')
    expect(html).toContain('s00001')
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
