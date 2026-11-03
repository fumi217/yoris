import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../i18n'
import { AreaTabs, type TabItem } from './AreaTabs'

const items: TabItem[] = [
  {
    to: '/staff',
    labelKey: 'layout.staff_tab.residents',
    icon: 'residents',
    isActive: (p) => p === '/staff',
  },
  {
    to: '/staff/messages',
    labelKey: 'layout.staff_tab.messages',
    icon: 'family-message',
    count: 3,
    isActive: (p) => p.startsWith('/staff/messages'),
  },
]

const render = (path: string) =>
  renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      <AreaTabs items={items} labelKey="layout.to_staff" />
    </MemoryRouter>,
  )

const text = (html: string) => html.replace(/<rt>.*?<\/rt>/g, '').replace(/<[^>]+>/g, '')

describe('AreaTabs', () => {
  it('選ばれたタブだけに aria-current="page" を付ける（色だけで示さない。1.4.1）', () => {
    const html = render('/staff/messages')

    expect(html.match(/aria-current="page"/g)).toHaveLength(1)
    expect(html).toMatch(/aria-current="page"[^>]*class="[^"]*font-bold/)
  })

  it('帯には名前を付ける（nav）', () => {
    expect(render('/staff')).toMatch(/<nav[^>]*aria-label="職員の画面"/)
  })

  it('件数は、赤い丸（飾り）と、読み上げ用の文字の両方で出す。0 件・なしは出さない', () => {
    const html = render('/staff')

    expect(html).toContain('aria-hidden="true"')
    expect(text(html)).toContain('3 件')
    expect(html.match(/rounded-full bg-danger/g)).toHaveLength(1)
  })

  it('押せる高さは 44px 以上', () => {
    expect(render('/staff')).toContain('min-h-14')
  })
})
