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

  it('時間がたっても、2 回目を受け付ける（5 秒で元に戻すのはやめた。#300）', () => {
    expect(canConfirm(1000, 1000 + 5_000)).toBe(true)
    expect(canConfirm(1000, 1000 + 10 * 60_000)).toBe(true)
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

  it('describedBy を渡すと、ボタンに aria-describedby が付く（渡さなければ付けない）', () => {
    expect(render({ describedBy: 'photo-7-desc' })).toContain('aria-describedby="photo-7-desc"')
    expect(render()).not.toContain('aria-describedby')
    // 決めている途中のボタンも、同じ説明につなぐ
    expect(
      render({ busy: true, busyKey: 'visit.cancelling', describedBy: 'photo-7-desc' }),
    ).toContain('aria-describedby="photo-7-desc"')
  })

  it('決めている途中は、その文言で押せない', () => {
    const html = render({ busy: true, busyKey: 'visit.cancelling' })

    expect(html).toContain('disabled=""')
    expect(html).toContain('しています')
  })
})
