import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../i18n'
import { ConfirmButton } from './ConfirmButton'
import { canConfirm, CONFIRM_MIN_MS } from './confirmTiming'

describe('canConfirm', () => {
  it('1 回目からすぐの 2 回目は受け付けない（素早い 2 回のタップで決まらない）', () => {
    expect(canConfirm(1000, 1000 + CONFIRM_MIN_MS - 1)).toBe(false)
    expect(canConfirm(1000, 1000 + CONFIRM_MIN_MS)).toBe(true)
  })
})

describe('ConfirmButton', () => {
  const render = (props: Partial<Parameters<typeof ConfirmButton>[0]> = {}) =>
    renderToStaticMarkup(
      <ConfirmButton
        labelKey="record_page.cancel"
        confirmKey="record_page.cancel_confirm"
        onConfirm={() => {}}
        {...props}
      />,
    )

  it('初めは、決める前の文言のボタンを 1 つだけ出す', () => {
    const html = render()

    expect(html.match(/<button/g)).toHaveLength(1)
    expect(html).toContain('この<ruby>記録')
    expect(html).not.toContain('やめる')
  })

  it('決めている途中は、その文言で押せない', () => {
    const html = render({ busy: true, busyKey: 'visit.cancelling' })

    expect(html).toContain('disabled=""')
    expect(html).toContain('しています')
  })
})
