import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { ApiError } from '../../api/client'
import { PortalButtonView } from './PortalButton'

// ふりがな（<rt>・<rp>）と、そのほかのタグを外した、画面の文字だけ
const textOf = (html: string) =>
  html.replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '').replace(/<[^>]*>/g, '')

const render = (props: Partial<Parameters<typeof PortalButtonView>[0]> = {}) =>
  renderToStaticMarkup(
    <PortalButtonView opening={false} error={null} onOpen={() => {}} {...props} />,
  )

describe('PortalButtonView', () => {
  it('お支払い方法の変更・解約・請求書の確認のボタンを 1 つ出す', () => {
    const html = render()

    expect(html.match(/<button/g)).toHaveLength(1)
    expect(textOf(html)).toContain('お支払い方法の変更・解約・請求書の確認')
    expect(textOf(html)).toContain('Stripeの画面が開きます')
    expect(html).not.toContain('role="alert"')
  })

  it('開いている間は、ボタンを押せなくする（二度押し対策）', () => {
    const html = render({ opening: true })

    expect(html).toContain('disabled')
    expect(textOf(html)).toContain('開いています')
  })

  it('開けなかったときは、そのエラーの文言を警告として出す', () => {
    const error = new ApiError(
      502,
      'payment_service_unavailable',
      'error.payment_service_unavailable',
    )

    const html = render({ error })

    expect(html).toContain('role="alert"')
    expect(textOf(html)).toContain('決済サービスの画面を開けませんでした')
  })
})
