import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ME_QUERY_KEY, type Me } from '../../auth/me'
import '../../i18n'
import { FamilyMorePage } from './FamilyMorePage'

// 家族の「その他」の見た目（#401）のテスト

const me: Me = { kind: 'family', role: null, display_name: '架空 花子さんの母', language: 'ja' }

function render() {
  const queryClient = new QueryClient()
  queryClient.setQueryData(ME_QUERY_KEY, me)
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <FamilyMorePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('FamilyMorePage の見た目', () => {
  it('見出し「その他」と、2 つのまとまりの見出しを出す', () => {
    const shown = text(render())

    expect(shown).toContain('その他')
    expect(shown).toContain('施設とのやりとり')
    expect(shown).toContain('アプリの設定')
    expect(shown.indexOf('施設とのやりとり')).toBeLessThan(shown.indexOf('アプリの設定'))
  })

  it('「お知らせ」「お問い合わせ」「設定」の行に、一言の説明と、右の矢印を出す', () => {
    const html = render()
    const shown = text(html)

    for (const [name, description, href] of [
      ['お知らせ', '届いたお知らせを見ます', '/family/notifications'],
      ['お問い合わせ', 'AI に質問できます。内容によっては、職員から回答します', '/family/inquiry'],
      ['設定', '通知とまとめの設定', '/family/settings'],
    ]) {
      expect(shown).toContain(name)
      expect(shown).toContain(description)
      expect(html).toContain(`href="${href}"`)
    }
    expect(html.match(/data-icon="chevron-right"/g)).toHaveLength(3)
  })

  it('面会予約・アルバムは、下のメニューに出るので、ここには出さない', () => {
    const html = render()

    expect(html).not.toContain('href="/family/visits"')
    expect(html).not.toContain('href="/family/album"')
  })

  it('「お知らせ」「お問い合わせ」は 1 つの白い面、「設定」と言語は、もう 1 つの白い面に入る', () => {
    const html = render()

    expect(html.match(/<ul class="[^"]*rounded-2xl/g)).toHaveLength(2)
    const second = html.slice(html.lastIndexOf('<ul class="'))
    expect(second).toContain('href="/family/settings"')
    expect(second).toContain('<select')
    expect(html.slice(0, html.lastIndexOf('<ul class="'))).toContain('href="/family/inquiry"')
  })

  it('言語の選びは、ラベルつき（label の for と select の id が同じ）で、押せる高さは 44px 以上', () => {
    const html = render()

    expect(html).toContain('for="family-language"')
    expect(html).toMatch(/<select[^>]*id="family-language"/)
    expect(html).toMatch(/<select[^>]*class="[^"]*min-h-11/)
    expect(text(html)).toContain('表示する言葉')
    // 言語の名前は、その言語で書く
    expect(html).toContain('Bahasa Indonesia')
  })

  it('ログアウトは、アイコンつきの独立したボタン（赤くしない）', () => {
    const html = render()
    const button = html.match(/<button[^>]*>.*?<\/button>/s)?.[0] ?? ''

    expect(text(button)).toBe('ログアウト')
    expect(button).toContain('data-icon="right-from-bracket"')
    expect(button).toContain('w-full')
    expect(button).not.toContain('red')
  })
})
