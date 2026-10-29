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
    // 同じ行き先（/staff）のリンクが、2 つに分かれていない
    expect(html.match(/href="\/staff"/g)).toHaveLength(1)
  })

  it('ロゴは、職員・管理画面の大きさ（高さ 32px）', () => {
    expect(render()).toMatch(/<img[^>]*class="[^"]*h-8/)
  })
})
