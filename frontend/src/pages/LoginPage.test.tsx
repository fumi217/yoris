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

  it('フォームを白いカードに載せ、入力欄の中も白にする（家族の画面と同じ。#447）', () => {
    const html = render()

    expect(html).toMatch(/<form[^>]*class="[^"]*rounded-2xl[^"]*border-card-line[^"]*bg-card/)
    const inputs = html.match(/<input[^>]*class="[^"]*"/g) ?? []
    expect(inputs).toHaveLength(2)
    // 幅と余白は、申込・完了の画面と同じ（max-w は上限だけなので、スマホでは画面の幅いっぱい）
    expect(html).toMatch(/<main[^>]*class="[^"]*max-w-xl/)
    for (const input of inputs) expect(input).toContain('bg-card')
  })
})
