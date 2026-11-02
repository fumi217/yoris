import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/client'
import '../../i18n'
import { Album, AlbumView } from './Album'
import { dayKindOf, type AlbumDay, type AlbumPage } from './albumView'
import { addDays, todayInJapan } from './visits/visitDates'

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

describe('アルバムの見た目（#412）', () => {
  it('見出し（h1）と一言の説明を出す', () => {
    const html = render([])

    expect(html).toMatch(/<h1 class="text-2xl[^"]*">/)
    expect(text(html)).toContain(
      '施設で撮影したお写真を掲載しています。写真を押すと、拡大して見ることができます。',
    )
    expect(text(html)).not.toContain('職員が載せた')
  })

  it('日の見出しに、枚数の印を出す', () => {
    const shown = text(render([{ date: '2026-11-05', photos: [photo(2), photo(1)] }]))

    expect(shown).toContain('11月5日')
    expect(shown).toContain('2枚')
  })

  it('今日・昨日は「今日（◯月◯日）」「昨日（◯月◯日）」、それ以外は日付と曜日', () => {
    const today = todayInJapan()
    const yesterday = addDays(today, -1)
    const shown = text(
      render([
        { date: today, photos: [photo(3)] },
        { date: yesterday, photos: [photo(2)] },
        { date: '2020-11-05', photos: [photo(1)] },
      ]),
    )

    expect(shown).toMatch(/今日（\d+月\d+日）/)
    expect(shown).toMatch(/昨日（\d+月\d+日）/)
    expect(shown).toContain('11月5日（木）')
    expect(dayKindOf(today, today)).toBe('today')
    expect(dayKindOf(yesterday, today)).toBe('yesterday')
    expect(dayKindOf('2020-11-05', today)).toBe('other')
  })

  it('日ごとに 1 つの白い面に、角丸の写真を 3 列で並べる。コメントは 2 行まで', () => {
    const html = render([{ date: '2026-11-05', photos: [photo(1, '花見')] }])

    expect(html).toMatch(/<ul class="[^"]*grid-cols-3[^"]*rounded-2xl[^"]*bg-card/)
    expect(html).toMatch(/<img[^>]*class="[^"]*rounded-xl/)
    expect(html).toMatch(/<p class="[^"]*line-clamp-2[^"]*">花見<\/p>/)
  })

  it('「もっと見る」は、矢印つきで、背景色と影のあるボタン', () => {
    const html = render([{ date: '2026-11-05', photos: [photo(1)] }], true)
    const button = html.match(/<button[^>]*shadow-sm[^>]*>.*?<\/button>/s)?.[0] ?? ''

    expect(button).toContain('bg-white')
    expect(button).toContain('data-icon="chevron-down"')
  })

  it('写真がないときは、アイコンと一言（案内）を、白い面の中に出す', () => {
    const html = render([])

    expect(html).toContain('data-icon="images"')
    expect(text(html)).toContain('職員が写真を載せると、ここに並びます')
  })
})
