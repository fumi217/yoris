import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Icon } from './Icon'

describe('Icon', () => {
  it('ふつうは飾り：読み上げない（aria-hidden）。名前は付けない（横に文字があるため）', () => {
    const html = renderToStaticMarkup(<Icon name="contact-book" />)

    expect(html).toContain('<svg')
    expect(html).toContain('aria-hidden="true"')
    expect(html).not.toContain('aria-label')
  })

  it('アイコンだけで意味を伝えるときは、名前を付けて読み上げる（aria-label。1.1.1）', () => {
    const html = renderToStaticMarkup(<Icon name="notifications" label="お知らせ" />)

    expect(html).toContain('role="img"')
    expect(html).toContain('aria-label="お知らせ"')
    expect(html).not.toContain('aria-hidden="true"')
  })

  it('色は文字と同じ（currentColor）、横幅は固定（並べたときにそろう）', () => {
    const html = renderToStaticMarkup(<Icon name="more" />)

    expect(html).toContain('fill="currentColor"')
    expect(html).toContain('fa-fw')
  })

  it('大きさなどの class は、呼ぶ側で足せる', () => {
    expect(renderToStaticMarkup(<Icon name="visits" className="text-lg text-primary" />)).toMatch(
      /class="[^"]*text-lg text-primary/,
    )
  })

  it('用途ごとに、別のアイコン（同じ用途は、いつも同じアイコン）', () => {
    const paths = (name: Parameters<typeof Icon>[0]['name']) =>
      renderToStaticMarkup(<Icon name={name} />).match(/<path[^>]*d="([^"]+)"/)?.[1]

    expect(paths('contact-book')).toBeTruthy()
    expect(paths('contact-book')).toBe(paths('contact-book'))
    expect(paths('contact-book')).not.toBe(paths('notifications'))
  })
})
