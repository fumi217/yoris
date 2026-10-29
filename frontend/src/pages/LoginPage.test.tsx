import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ME_QUERY_KEY } from '../auth/me'
import '../i18n'
import { LoginPage } from './LoginPage'

function render() {
  const queryClient = new QueryClient()
  // ログインしていない（401 のとき、ログイン中の人は null）
  queryClient.setQueryData(ME_QUERY_KEY, null)
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage', () => {
  it('左上にロゴを出す。ログインの前なので、リンクにしない', () => {
    const html = render()
    const header = html.match(/<header[^>]*>(.*?)<\/header>/)?.[1] ?? ''

    expect(header).toContain('alt="YORIS"')
    expect(header).not.toContain('<a ')
  })

  it('画面の題（h1）は「ログイン」。アプリの名前は、ロゴが伝える（YORIS を二重に出さない）', () => {
    const html = render()
    const h1 = html.match(/<h1[^>]*>(.*?)<\/h1>/)?.[1] ?? ''

    expect(h1.replace(/<[^>]+>/g, '')).toBe('ログイン')
  })
})
