import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { AlbumUploadView } from './AlbumUpload'
import { addFiles, updateItem, type UploadItem } from './albumUploadLogic'

const file = (type = 'image/png', size = 100) => ({ type, size }) as File

const render = (items: UploadItem[] = [], extra: { skipped?: number; sending?: boolean } = {}) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <AlbumUploadView
        residentId="5"
        resident={{ id: 5, display_name: '佐藤さんの母', room: '101' } as never}
        items={items}
        previews={Object.fromEntries(items.map((item) => [item.id, `blob:preview-${item.id}`]))}
        skipped={extra.skipped ?? 0}
        sending={extra.sending ?? false}
        onPick={() => {}}
        onComment={() => {}}
        onRemove={() => {}}
        onRetry={() => {}}
        onSend={() => {}}
      />
    </MemoryRouter>,
  )

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('AlbumUploadView', () => {
  it('「撮る」と「写真から選ぶ」を出す。JPG・PNG だけ選べ、カメラは capture、選ぶは複数枚', () => {
    const html = render()

    expect(text(html)).toContain('撮る')
    expect(text(html)).toContain('写真から選ぶ')
    expect(html.match(/accept="image\/jpeg,image\/png"/g)).toHaveLength(2)
    expect(html).toContain('capture="environment"')
    expect(html.match(/multiple/g)).toHaveLength(1)
  })

  it('写真を選ぶ前は、「送る」を出さない。10 枚までの案内と、戻るリンクを出す', () => {
    const html = render()

    expect(text(html)).not.toContain('送る')
    expect(text(html)).toContain('10 枚まで')
    expect(html).toContain('href="/staff/residents/5"')
  })

  it('選んだ写真に、プレビューと、任意で 100 文字までのコメント欄を出す', () => {
    const { items } = addFiles([], [file(), file()], 1)
    const html = render(items)

    expect(html).toContain('src="blob:preview-1"')
    expect(html).toContain('src="blob:preview-2"')
    expect(html.match(/maxLength="100"/g)).toHaveLength(2)
    expect(text(html)).toContain('なくてもよい')
    expect(text(html)).toContain('0 / 2 枚を載せました')
  })

  it('状態は、印と文字で出す（色だけに頼らない）', () => {
    const { items } = addFiles([], [file(), file(), file()], 1)
    const mixed = updateItem(
      updateItem(updateItem(items, 1, { status: 'done' }), 2, { status: 'sending' }),
      3,
      { status: 'failed', errorKey: 'error.server_error', retryable: true },
    )
    const html = render(mixed)

    expect(text(html)).toContain('✔載せました')
    expect(text(html)).toContain('送っています')
    expect(text(html)).toContain('⚠載せられませんでした')
    expect(text(html)).toContain('1 / 3 枚を載せました')
  })

  it('失敗した写真にだけ「もう一度送る」を出す', () => {
    const { items } = addFiles([], [file(), file()], 1)
    const html = render(
      updateItem(items, 2, { status: 'failed', errorKey: 'error.server_error', retryable: true }),
    )

    expect(text(html).match(/もう一度送る/g)).toHaveLength(1)
  })

  it('画面で断った写真（大きすぎる・形式が違う）は、理由を出し、送り直しもコメント欄も出さない', () => {
    const { items } = addFiles([], [file('image/png', 20 * 1024 * 1024)], 1)
    const html = render(items)

    expect(text(html)).toContain('10MB を超える写真は載せられません')
    expect(text(html)).not.toContain('もう一度送る')
    expect(html).not.toContain('maxLength')
  })

  it('画像でないファイル（PDF）は、壊れた画像ではなく、📄 を出す', () => {
    const { items } = addFiles([], [file('application/pdf')], 1)
    const html = render(items)

    expect(html).not.toContain('<img')
    expect(html).toContain('📄')
    expect(text(html)).toContain('JPG か PNG の写真だけ載せられます')
  })

  it('10 枚を超えて選んだときは、超えた分の案内を出す', () => {
    const html = render([], { skipped: 3 })

    expect(text(html)).toContain('一度に 10 枚までです。超えた 3 枚は選ばれていません')
  })

  it('送っているあいだ、「送る」は押せない（二重に送らない）', () => {
    const { items } = addFiles([], [file()], 1)

    // 待ちの写真だけがあるとき、押せないボタンは「送る」だけ
    expect(render(items, { sending: true })).toContain('disabled=""')
    expect(render(items, { sending: false })).not.toContain('disabled=""')
  })

  it('コメントは、文字としてだけ扱う（入力欄の値は、HTML として解釈されない）', () => {
    const { items } = addFiles([], [file()], 1)
    const html = render(updateItem(items, 1, { comment: '<script>alert(1)</script>' }))

    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })
})
