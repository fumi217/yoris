import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ME_QUERY_KEY, type Me } from '../auth/me'
import '../i18n'
import { StaffHeader } from './StaffHeader'

const me: Me = { kind: 'staff', role: 'leader', display_name: 'テスト職員', language: 'ja' }

function render() {
  const queryClient = new QueryClient()
  queryClient.setQueryData(ME_QUERY_KEY, me)
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StaffHeader
          homeTo="/staff"
          titleKey="layout.to_staff"
          otherArea="admin"
          otherTo="/admin"
          otherKey="layout.to_admin"
          tabs={[
            {
              to: '/staff',
              labelKey: 'layout.staff_tab.residents',
              icon: 'residents',
              isActive: (path) => path === '/staff',
            },
            {
              to: '/staff/messages',
              labelKey: 'layout.staff_tab.messages',
              icon: 'family-message',
              count: 2,
              isActive: (path) => path.startsWith('/staff/messages'),
            },
          ]}
          tabsLabelKey="layout.to_staff"
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('StaffHeader', () => {
  it('左にロゴと題を出す。ロゴと題は、同じ行き先の 1 つのリンク（2.4.4）', () => {
    const html = render()

    const link = html.match(/<a [^>]*href="\/staff"[^>]*>(.*?)<\/a>/)?.[1] ?? ''
    expect(link).toContain('alt="YORIS"')
    expect(link).toContain('画面')
    // ロゴと題は、同じ行き先（/staff）の 1 つのリンク。タブの「入居者一覧」は、その下の段（別の部品）
    expect(link).toContain('画面')
    expect(html.match(/href="\/staff"/g)).toHaveLength(2)
  })

  it('ロゴは、職員・管理画面の大きさ（高さ 32px）', () => {
    expect(render()).toMatch(/<img[^>]*class="[^"]*h-8/)
  })

  it('名前と役割を出す（名前の頭の 1 文字の丸は、読み上げない）', () => {
    const html = render()

    expect(html).toContain('テスト職員')
    expect(html).toContain('リーダー')
    expect(html).toMatch(/aria-hidden="true"[^>]*>テ</)
  })

  it('下の段に、行き先のタブの帯を出す（職員の画面）', () => {
    const html = render()

    expect(html).toMatch(/<nav[^>]*aria-label="職員の画面"/)
    expect(html).toContain('href="/staff/messages"')
  })

  it('言語とログアウトは、名前のボタンで開く段の中（はじめは閉じている。画面の上に重ねない）', () => {
    const html = render()

    expect(html).toMatch(
      /<button[^>]*aria-expanded="false"[^>]*aria-controls="staff-account-panel"/,
    )
    expect(html).toMatch(/<div id="staff-account-panel" hidden=""/)
  })
})
