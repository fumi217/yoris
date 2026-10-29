import { describe, expect, it } from 'vitest'
import { dayParts, mergeAlbumPages, nextBefore, type AlbumPage, type AlbumPhoto } from './albumView'
import { familyMoreMenu, visibleMoreMenu } from './menu'

const photo = (id: number): AlbumPhoto => ({
  id,
  posted_at: '2026-11-05T03:00:00Z',
  comment: null,
  url: `/api/files/${id}`,
})

describe('mergeAlbumPages', () => {
  it('ページの境目で同じ日が続くときは、1 つの日にまとめる', () => {
    const pages: AlbumPage[] = [
      {
        days: [
          { date: '2026-11-06', photos: [photo(5)] },
          { date: '2026-11-05', photos: [photo(4)] },
        ],
        next_before: 4,
      },
      {
        days: [
          { date: '2026-11-05', photos: [photo(3), photo(2)] },
          { date: '2026-11-04', photos: [photo(1)] },
        ],
        next_before: null,
      },
    ]

    const days = mergeAlbumPages(pages)

    expect(days.map((day) => day.date)).toEqual(['2026-11-06', '2026-11-05', '2026-11-04'])
    expect(days[1].photos.map((p) => p.id)).toEqual([4, 3, 2])
  })

  it('元のページのデータを書き換えない', () => {
    const first: AlbumPage = { days: [{ date: '2026-11-05', photos: [photo(2)] }], next_before: 2 }
    const second: AlbumPage = {
      days: [{ date: '2026-11-05', photos: [photo(1)] }],
      next_before: null,
    }

    mergeAlbumPages([first, second])

    expect(first.days[0].photos.map((p) => p.id)).toEqual([2])
  })

  it('写真が 1 枚もないときは、空', () => {
    expect(mergeAlbumPages([{ days: [], next_before: null }])).toEqual([])
    expect(mergeAlbumPages([])).toEqual([])
  })
})

describe('dayParts', () => {
  it('日付を、見出しに出す月と日にする（0 を付けない）', () => {
    expect(dayParts('2026-11-05')).toEqual({ month: '11', day: '5' })
    expect(dayParts('2026-01-31')).toEqual({ month: '1', day: '31' })
  })
})

describe('nextBefore', () => {
  it('続きがあるときだけ、before を返す', () => {
    expect(nextBefore({ days: [], next_before: 7 })).toBe(7)
    expect(nextBefore({ days: [], next_before: null })).toBeUndefined()
  })
})

describe('visibleMoreMenu', () => {
  const hasAlbum = (items: { to: string }[]) => items.some((item) => item.to === '/family/album')

  it('アルバムは、「見せる」と分かったときだけ出る', () => {
    expect(hasAlbum(visibleMoreMenu({ album: true }))).toBe(true)
    expect(hasAlbum(visibleMoreMenu({ album: false }))).toBe(false)
  })

  it('API の答えが来るまでは、アルバムを出さない（出たり消えたりしない）', () => {
    expect(hasAlbum(visibleMoreMenu(undefined))).toBe(false)
  })

  it('アルバム以外の項目は、いつも出る', () => {
    const others = familyMoreMenu.filter((item) => item.to !== '/family/album')

    expect(visibleMoreMenu({ album: false })).toEqual(others)
    expect(visibleMoreMenu(undefined)).toEqual(others)
  })
})
