import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ME_QUERY_KEY, type Me } from '../../auth/me'
import '../../i18n'
import { FamilyLayout } from './FamilyLayout'

const me: Me = { kind: 'family', role: null, display_name: '架空 太郎', language: 'ja' }

function render(path = '/family', features?: { album: boolean }) {
  const queryClient = new QueryClient()
  queryClient.setQueryData(ME_QUERY_KEY, me)
  if (features) queryClient.setQueryData(['family', 'features'], features)
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
    expect(header).toContain('架空 太郎<span class="text-[0.85em]">さん</span>')
    // ロゴが先（左）、呼び名があと（右）
    expect(header.indexOf('alt="YORIS"')).toBeLessThan(header.indexOf('架空 太郎'))
  })

  it('呼び名が長くても、横にあふれない（省略する。幅 320px）', () => {
    expect(render()).toMatch(/<p class="[^"]*truncate[^"]*">架空 太郎/)
  })

  it('ロゴの高さは 28px（h-7）', () => {
    expect(render()).toMatch(/<img[^>]*class="[^"]*h-7/)
  })
})

describe('FamilyLayout の下のメニューのアイコン（#379）', () => {
  it('すべて、Font Awesome のアイコン（svg。飾りなので読み上げない）。絵文字は出さない。アルバムが出るときは 5 つ', () => {
    const nav = (html: string) => html.match(/<nav[^>]*>(.*?)<\/nav>/)?.[1] ?? ''
    const shown = nav(render('/family', { album: true }))

    expect(shown.match(/<svg[^>]*aria-hidden="true"/g)).toHaveLength(5)
    expect(shown).not.toMatch(/[\u{1F300}-\u{1FAFF}☰]/u)
  })

  it('下は 連絡帳・知りたいこと・面会予約・アルバム・その他。アルバムは、見せないときは出ない（答えが来るまでも出さない）', () => {
    const nav = (html: string) => html.match(/<nav[^>]*>(.*?)<\/nav>/)?.[1] ?? ''
    const text = (html: string) =>
      nav(html)
        .replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '')
        .replace(/<[^>]+>/g, '')

    expect(text(render('/family', { album: true }))).toBe(
      '連絡帳知りたいこと面会予約アルバムその他',
    )
    expect(text(render('/family', { album: false }))).toBe('連絡帳知りたいこと面会予約その他')
    expect(text(render('/family'))).toBe('連絡帳知りたいこと面会予約その他')
  })

  it('「お知らせ」「お問い合わせ」は、下に出ない（「その他」の中）。「知りたいこと」は、下に出る', () => {
    const nav = render('/family', { album: true }).match(/<nav[^>]*>(.*?)<\/nav>/)?.[1] ?? ''

    // ふりがな（<rt>・<rp>）と印を除いた、画面に出る文字
    const shown = nav.replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '').replace(/<[^>]+>/g, '')

    expect(shown).not.toContain('お知らせ')
    expect(shown).not.toContain('お問い合わせ')
    expect(shown).toContain('知りたいこと')
  })

  it('「その他」の中の画面（お知らせなど）を開いているときは、「その他」が選ばれた表示になる', () => {
    const nav = render('/family/notifications').match(/<nav[^>]*>(.*?)<\/nav>/)?.[1] ?? ''

    expect(nav).toMatch(/class="[^"]*font-bold text-primary[^"]*"[^>]*>(?:(?!<\/a>).)*その/)
  })

  it('選んでいるものは太字・YORIS の青、ほかはブルーグレー', () => {
    const nav = render('/family/requests').match(/<nav[^>]*>(.*?)<\/nav>/)?.[1] ?? ''

    expect(nav).toMatch(/class="[^"]*font-bold text-primary[^"]*"[^>]*>(?:(?!<\/a>).)*知/)
    expect(nav).toContain('text-ink-sub')
  })
})
