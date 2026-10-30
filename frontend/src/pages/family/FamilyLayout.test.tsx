import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ME_QUERY_KEY, type Me } from '../../auth/me'
import '../../i18n'
import { FamilyLayout } from './FamilyLayout'

const me: Me = { kind: 'family', role: null, display_name: '架空 太郎さんの母', language: 'ja' }

function render(path = '/family') {
  const queryClient = new QueryClient()
  queryClient.setQueryData(ME_QUERY_KEY, me)
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <FamilyLayout />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('FamilyLayout の上の枠', () => {
  it('左にロゴ（押すとホームへ）、右に入居者の呼び名を出す', () => {
    const html = render()
    const header = html.match(/<header[^>]*>(.*?)<\/header>/)?.[1] ?? ''

    expect(header).toMatch(/<a [^>]*href="\/family"[^>]*><img[^>]*alt="YORIS"/)
    expect(header).toContain('架空 太郎さんの母')
    // ロゴが先（左）、呼び名があと（右）
    expect(header.indexOf('alt="YORIS"')).toBeLessThan(header.indexOf('架空 太郎さんの母'))
  })

  it('呼び名が長くても、横にあふれない（省略する。幅 320px）', () => {
    expect(render()).toMatch(/<p class="[^"]*truncate[^"]*">架空 太郎さんの母/)
  })

  it('ロゴの高さは 28px（h-7）', () => {
    expect(render()).toMatch(/<img[^>]*class="[^"]*h-7/)
  })
})

describe('FamilyLayout の下のメニューのアイコン（#379）', () => {
  it('5 つとも、Font Awesome のアイコン（svg。飾りなので読み上げない）。絵文字は出さない', () => {
    const html = render()
    const nav = html.match(/<nav[^>]*>(.*?)<\/nav>/)?.[1] ?? ''

    expect(nav.match(/<svg[^>]*aria-hidden="true"/g)).toHaveLength(5)
    expect(nav).not.toMatch(/[\u{1F300}-\u{1FAFF}☰]/u)
  })

  it('選んでいるものは太字・YORIS の青、ほかはブルーグレー', () => {
    const nav = render('/family/notifications').match(/<nav[^>]*>(.*?)<\/nav>/)?.[1] ?? ''

    expect(nav).toMatch(/class="[^"]*font-bold text-primary[^"]*"[^>]*>(?:(?!<\/a>).)*お/)
    expect(nav).toContain('text-ink-sub')
  })
})
