import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { UnconfirmedFlagFilter } from './UnconfirmedFlagFilter'

function render(count: number, active: boolean): string {
  return renderToStaticMarkup(
    <UnconfirmedFlagFilter count={count} active={active} onToggle={() => {}} />,
  )
}

// ふりがな（<ruby>・<rt>・<rp>）を外して、画面に出る文字だけで比べる
function text(html: string): string {
  return html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')
}

describe('確かめていない目印の絞り込み（spec 006 の T014・FR-003）', () => {
  it('「確かめていない目印：◯件」を出す', () => {
    expect(text(render(3, false))).toBe('確かめていない目印：3 件')
  })

  it('絞っていないときは押された状態にしない', () => {
    const html = render(3, false)

    expect(html).toContain('aria-pressed="false"')
    expect(text(html)).not.toContain('✔')
  })

  it('絞っているときは、色だけでなく ✔ と押された状態でも示す', () => {
    const html = render(3, true)

    expect(html).toContain('aria-pressed="true"')
    expect(text(html)).toBe('✔ 確かめていない目印：3 件')
  })

  it('目印がなくて絞っていないときは押せない', () => {
    expect(render(0, false)).toContain('disabled=""')
    expect(text(render(0, false))).toBe('確かめていない目印：0 件')
  })

  it('目印があるとき、絞っているあいだは件数が 0 になっても、押して戻せる', () => {
    expect(render(3, false)).not.toContain('disabled=""')
    expect(render(0, true)).not.toContain('disabled=""')
  })

  it('押せる大きさ（44px 以上）にしている', () => {
    expect(render(1, false)).toContain('min-h-11')
  })
})
