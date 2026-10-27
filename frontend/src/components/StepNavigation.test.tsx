import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../i18n'
import { StepNavigation } from './StepNavigation'

const steps = [
  { titleKey: 'steps.signup.entry' },
  { titleKey: 'steps.signup.payment' },
  { titleKey: 'steps.signup.done' },
]

// ふりがな（<rt>・<rp>）と、そのほかのタグを外した、画面の文字だけ
const textOf = (html: string) =>
  html.replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '').replace(/<[^>]*>/g, '')

const render = (current: number, errorStep?: number) =>
  renderToStaticMarkup(
    <StepNavigation labelKey="steps.label" steps={steps} current={current} errorStep={errorStep} />,
  )

describe('StepNavigation', () => {
  it('3 つのステップを、番号と名前つきで並べる', () => {
    const text = textOf(render(1))

    expect(render(1).match(/<li /g)).toHaveLength(3)
    expect(text).toContain('お申し込み')
    expect(text).toContain('お支払い')
    expect(text).toContain('完了')
  })

  it('今のステップにだけ aria-current を付ける', () => {
    const html = render(2)

    expect(html.match(/aria-current="true"/g)).toHaveLength(1)
    expect(html).toMatch(/<li aria-current="true" data-state="current"[^>]*>(?:(?!<\/li>).)*お/s)
  })

  it('全体の進み具合を、見えない文で伝える', () => {
    expect(textOf(render(2))).toContain('全3ステップ中、2ステップ目')
  })

  it('前のステップは完了（チェック）、後ろはまだ', () => {
    const html = render(3)

    expect(html.match(/data-state="completed"/g)).toHaveLength(2)
    expect(html.match(/data-state="current"/g)).toHaveLength(1)
    expect(render(1).match(/data-state="upcoming"/g)).toHaveLength(2)
    expect(html).toContain('✓')
  })

  it('うまくいかなかったステップには ! を付け、エラーと伝える', () => {
    const html = render(2, 2)

    expect(html).toContain('data-state="error"')
    expect(html).toContain('!')
    expect(textOf(html)).toContain('エラー')
  })
})
