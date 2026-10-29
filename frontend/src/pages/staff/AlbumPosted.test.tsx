import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { AlbumPosted, type PostedPhoto, type StaffAlbum } from './AlbumPosted'

const photo = (id: number, comment: string | null = null): PostedPhoto => ({
  id,
  posted_at: '2026-11-05T03:00:00Z',
  comment,
  url: `/api/files/${id}`,
})

const render = (
  album: StaffAlbum | undefined,
  extra: Partial<Parameters<typeof AlbumPosted>[0]> = {},
) =>
  renderToStaticMarkup(
    <AlbumPosted
      album={album}
      loadErrorKey={null}
      deletingId={null}
      noticeKey={null}
      deleteErrorKey={null}
      onDelete={() => {}}
      {...extra}
    />,
  )

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('AlbumPosted', () => {
  it('載せた写真がないときは「まだ載せた写真はありません」を出す', () => {
    const html = render({ family_visible: true, photos: [] })

    expect(text(html)).toContain('まだ載せた写真はありません')
    expect(html).not.toContain('<img')
  })

  it('写真ごとに、削除のボタンを出す。写真は枠の大きさを先に決め、画面に出るときに読む', () => {
    const html = render({ family_visible: true, photos: [photo(2), photo(1)] })

    expect(html.match(/<img/g)).toHaveLength(2)
    expect(html.match(/削除する|さくじょ/g)?.length).toBeGreaterThanOrEqual(2)
    expect(html).toContain('loading="lazy"')
    expect(html).toContain('aspect-square')
    expect(html).toContain('src="/api/files/2"')
  })

  it('コメントは、文字としてだけ出す（HTML として解釈しない）', () => {
    const html = render({
      family_visible: true,
      photos: [photo(1, '<b>運動会</b><script>alert(1)</script>')],
    })

    expect(html).not.toContain('<b>運動会</b>')
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;b&gt;運動会&lt;/b&gt;')
  })

  it('家族に見せていない設定のときだけ「いま家族には見せていません」を出す（FR-016）', () => {
    const hidden = render({ family_visible: false, photos: [photo(1)] })
    const shown = render({ family_visible: true, photos: [photo(1)] })

    expect(text(hidden)).toContain('いま家族には見せていません')
    expect(text(shown)).not.toContain('いま家族には見せていません')
  })

  it('削除の結果の知らせを出す（削除しました／その写真は、もう削除されています）', () => {
    const album = { family_visible: true, photos: [] }

    expect(text(render(album, { noticeKey: 'album_upload.deleted' }))).toContain('削除しました')
    expect(text(render(album, { noticeKey: 'album_upload.already_deleted' }))).toContain(
      'その写真は、もう削除されています',
    )
  })

  it('「削除する」は、どの写真のものか読み上げで分かるように、コメントか載せた日時につなぐ', () => {
    const html = render({
      family_visible: true,
      photos: [photo(2, '運動会で、玉入れ'), photo(1, null)],
    })

    // コメントがある写真：見えているコメントにつなぐ
    expect(html).toContain('aria-describedby="album-photo-2-desc"')
    expect(html).toMatch(/<p id="album-photo-2-desc"[^>]*>運動会で、玉入れ<\/p>/)
    // コメントがない写真：画面には出さない説明（載せた日時。日本時間）につなぐ
    expect(html).toContain('aria-describedby="album-photo-1-desc"')
    expect(html).toMatch(/<p id="album-photo-1-desc" class="sr-only">/)
    expect(text(html.slice(html.indexOf('id="album-photo-1-desc"')))).toContain(
      '11月5日 12:00 に載せた写真',
    )
  })

  it('削除に失敗したときは、写真を残し、エラーの文を出す', () => {
    const html = render(
      { family_visible: true, photos: [photo(1)] },
      { deleteErrorKey: 'error.server_error' },
    )

    expect(html).toContain('role="alert"')
    expect(html.match(/<img/g)).toHaveLength(1)
  })

  it('削除している途中は、押せない（二重に送らない）', () => {
    const html = render({ family_visible: true, photos: [photo(1), photo(2)] }, { deletingId: 1 })

    // 削除している写真は文言が変わり、ほかの写真のボタンも押せない
    expect(text(html)).toContain('削除しています')
    expect(html).toContain('disabled')
  })

  it('一覧をまだ 1 枚も読めていないときは、読めなかった文を出す（載せる部分は使える）', () => {
    const html = render(undefined, { loadErrorKey: 'error.server_error' })

    expect(html).toContain('role="alert"')
    expect(html).not.toContain('<img')
  })
})
