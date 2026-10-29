import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/client'
import '../../i18n'
import { Album, AlbumView } from './Album'
import type { AlbumDay, AlbumPage } from './albumView'

// Album.tsx の ALBUM_KEY と同じ（コンポーネントのファイルからは定数を出さない決まり）
const ALBUM_KEY = ['family', 'album']

const photo = (id: number, comment: string | null = null) => ({
  id,
  posted_at: '2026-11-05T03:00:00Z',
  comment,
  url: `/api/files/${id}`,
})

const render = (days: AlbumDay[], hasMore = false) =>
  renderToStaticMarkup(
    <AlbumView days={days} hasMore={hasMore} loadingMore={false} onMore={() => {}} />,
  )

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('AlbumView', () => {
  it('写真が 1 枚もないときは「まだ写真はありません」を出す', () => {
    const html = render([])

    expect(text(html)).toContain('まだ写真はありません')
    expect(html).not.toContain('<img')
  })

  it('載せた日ごとに見出しを出し、新しい日が上に並ぶ', () => {
    const html = render([
      { date: '2026-11-06', photos: [photo(3)] },
      { date: '2026-11-05', photos: [photo(2), photo(1)] },
    ])

    const shown = text(html)
    expect(shown).toContain('11月6日')
    expect(shown.indexOf('11月6日')).toBeLessThan(shown.indexOf('11月5日'))
    expect(html.match(/<img/g)).toHaveLength(3)
  })

  it('写真は、枠の大きさを先に決め、画面に出るときに読む（サムネイルは作らない）', () => {
    const html = render([{ date: '2026-11-05', photos: [photo(7)] }])

    expect(html).toContain('src="/api/files/7"')
    expect(html).toContain('loading="lazy"')
    expect(html).toContain('aspect-square') // 枠の大きさ（loading="lazy" が、画面の外まで読み込まないため）
    expect(html).not.toContain('thumb')
  })

  it('コメントは、文字としてだけ出す（HTML として解釈しない）', () => {
    const html = render([
      { date: '2026-11-05', photos: [photo(1, '<b>運動会</b><script>alert(1)</script>')] },
    ])

    expect(html).not.toContain('<b>運動会</b>')
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;b&gt;運動会&lt;/b&gt;')
  })

  it('コメントがない写真には、コメントの欄を出さない', () => {
    const html = render([{ date: '2026-11-05', photos: [photo(1, null)] }])

    expect(html).not.toContain('break-words')
  })

  it('続きがあるときだけ「もっと見る」を出す', () => {
    const days = [{ date: '2026-11-05', photos: [photo(1)] }]

    expect(text(render(days, true))).toContain('もっと見る')
    expect(text(render(days, false))).not.toContain('もっと見る')
  })

  it('家族の画面なので、ふりがなは出さない（辞書のふりがなの印も、そのまま出さない）', () => {
    const html = render([{ date: '2026-11-05', photos: [photo(1)] }])

    expect(html).not.toContain('{')
  })
})

describe('Album の読み込みの失敗', () => {
  /** 取得の結果が「失敗」になっている状態を、最初から用意して出す（画面の操作はしない）。 */
  const renderFailed = (pages: AlbumPage[]) => {
    // 画面を出すときに読み直し（＝「読み込み中」に戻る）が始まらないようにして、失敗の状態を見る
    const queryClient = new QueryClient({
      defaultOptions: { queries: { staleTime: Infinity, retryOnMount: false } },
    })
    queryClient
      .getQueryCache()
      .build(queryClient, { queryKey: ALBUM_KEY })
      .setState({
        data: pages.length > 0 ? { pages, pageParams: pages.map((_, i) => i) } : undefined,
        status: 'error',
        error: new ApiError(500, 'server_error', 'error.server_error'),
      })
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <Album />
      </QueryClientProvider>,
    )
  }

  it('「もっと見る」などの読み込みが失敗しても、見ていた写真を消さず、エラーの文を足す', () => {
    const html = renderFailed([
      { days: [{ date: '2026-11-05', photos: [photo(1), photo(2)] }], next_before: 2 },
    ])

    expect(html.match(/<img/g)).toHaveLength(2)
    expect(text(html)).toContain('うまくいきませんでした')
  })

  it('最初の読み込みが失敗したとき（写真がまだ 1 枚もない）は、エラーの文だけを出す', () => {
    const html = renderFailed([])

    expect(html).not.toContain('<img')
    expect(text(html)).toContain('うまくいきませんでした')
  })
})
