import { describe, expect, it } from 'vitest'
import { familyMainMenu, familyMoreMenu, familyTitleKey } from './menu'

describe('familyTitleKey（ブラウザのタブの題に使う名前）', () => {
  it('ホームは連絡帳、「☰ その他」は「その他」', () => {
    expect(familyTitleKey('/family')).toBe('layout.family_menu.contact_book')
    expect(familyTitleKey('/family/')).toBe('layout.family_menu.contact_book')
    expect(familyTitleKey('/family/more')).toBe('layout.family_menu.more')
  })

  it('下のメニューと「☰ その他」の中の画面は、メニューの名前', () => {
    for (const item of [...familyMainMenu, ...familyMoreMenu]) {
      expect(familyTitleKey(item.to)).toBe(item.labelKey)
    }
  })

  it('メニューの下の画面（例：/family/requests/3）も、そのメニューの名前', () => {
    expect(familyTitleKey('/family/requests/3')).toBe('layout.family_menu.requests')
  })

  it('メニューにない画面は null（アプリの名前だけになる）', () => {
    expect(familyTitleKey('/family/unknown')).toBeNull()
  })
})
