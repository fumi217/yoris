import { describe, expect, it } from 'vitest'
import { familyMainMenu, familyMoreMenu, familyTitleKey } from './menu'

describe('familyTitleKey（ブラウザのタブの題に使う名前）', () => {
  it('ホームは連絡帳、「その他」は「その他」', () => {
    expect(familyTitleKey('/family')).toBe('layout.family_menu.contact_book')
    expect(familyTitleKey('/family/')).toBe('layout.family_menu.contact_book')
    expect(familyTitleKey('/family/more')).toBe('layout.family_menu.more')
  })

  it('下のメニューと「その他」の中の画面は、メニューの名前', () => {
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

describe('メニューのアイコン（#379）', () => {
  it('下のメニューと「その他」の中の項目は、すべてアイコンの名前を持ち、絵文字は使わない', () => {
    const emoji = /[\u{1F300}-\u{1FAFF}☀-➿⭐]/u
    for (const item of [...familyMainMenu, ...familyMoreMenu]) {
      expect(item.icon).toMatch(/^[a-z-]+$/)
      expect(item.icon).not.toMatch(emoji)
    }
  })

  it('同じ用途は同じアイコン：下のメニューは、すべて別のアイコン', () => {
    const icons = familyMainMenu.map((item) => item.icon)
    expect(new Set(icons).size).toBe(icons.length)
  })
})

describe('メニューの並び（spec 001 の Session 2026-10-30。#396）', () => {
  it('下は 連絡帳・知りたいこと・面会予約・アルバム。お知らせ・お問い合わせ・設定は「その他」の中', () => {
    expect(familyMainMenu.map((item) => item.to)).toEqual([
      '/family',
      '/family/requests',
      '/family/visits',
      '/family/album',
    ])
    expect(familyMoreMenu.map((item) => item.to)).toEqual([
      '/family/notifications',
      '/family/inquiry',
      '/family/settings',
    ])
  })

  it('下は、「その他」を足して 5 つまで', () => {
    expect(familyMainMenu.length + 1).toBeLessThanOrEqual(5)
  })
})
