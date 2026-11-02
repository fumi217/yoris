import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ME_QUERY_KEY, refetchAfterLanguageChange, type Me } from '../auth/me'
import '../i18n'
import { LanguageSwitcher } from './LanguageSwitcher'

function render(me: Me | null) {
  const queryClient = new QueryClient()
  queryClient.setQueryData(ME_QUERY_KEY, me)
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <LanguageSwitcher />
    </QueryClientProvider>,
  )
}

const staff: Me = { kind: 'staff', role: 'leader', display_name: 'テスト職員', language: 'ja' }

describe('LanguageSwitcher', () => {
  it('3 つの言語を、それぞれの言語の名前で出す', () => {
    const html = render(staff)

    expect(html).toContain('日本語')
    expect(html).toContain('Bahasa Indonesia')
    expect(html).toContain('English')
  })

  it('今のアカウントの言語を選んだ状態にする', () => {
    const html = render({ ...staff, language: 'id' })

    expect(html).toMatch(/<option value="id" selected="">/)
    expect(html).not.toMatch(/<option value="ja" selected="">/)
  })

  it('ログインしていないときは出さない', () => {
    expect(render(null)).toBe('')
  })

  it('言語を変えたら、ログイン中の人以外の取得済みの一覧を取り直す（名前の言語が変わるため。#389）', async () => {
    const queryClient = new QueryClient()
    queryClient.setQueryData(ME_QUERY_KEY, staff)
    queryClient.setQueryData(['staff', 'residents'], { residents: [] })
    queryClient.setQueryData(['family', 'contact-book'], {})

    await refetchAfterLanguageChange(queryClient)

    expect(queryClient.getQueryState(ME_QUERY_KEY)?.isInvalidated).toBe(false)
    expect(queryClient.getQueryState(['staff', 'residents'])?.isInvalidated).toBe(true)
    expect(queryClient.getQueryState(['family', 'contact-book'])?.isInvalidated).toBe(true)
  })
})
