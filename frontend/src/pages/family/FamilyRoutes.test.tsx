import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ME_QUERY_KEY, type Me } from '../../auth/me'
import '../../i18n'
import FamilyRoutes from './FamilyRoutes'

const family: Me = { kind: 'family', role: null, display_name: '佐藤さんの母', language: 'ja' }

/** ログイン中の家族を先に入れておき（/api/me を呼ばない）、家族の画面をその URL で出す。 */
function renderFamily(path: string) {
  const queryClient = new QueryClient()
  queryClient.setQueryData(ME_QUERY_KEY, family)
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/family/*" element={<FamilyRoutes />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('FamilyRoutes のふりがな（#260）', () => {
  it('家族の画面（FamilyRoutes の中）では、枠・メニューも含めて、ふりがなを出さない', () => {
    // 「その他」は、API を呼ばずに辞書の文言（面会・アルバム・設定・ログアウト）と下のメニューを出す
    const html = renderFamily('/family/more')

    expect(html).toContain('面会')
    expect(html).toContain('連絡帳')
    expect(html).not.toContain('<ruby>')
    expect(html).not.toContain('<rt>')
  })
})
