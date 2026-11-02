import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it } from 'vitest'
import i18n from '../i18n'
import { FuriganaContext } from '../i18n/furigana'
import { ResidentFamily, ResidentName } from './ResidentName'

const RUBY = '{佐藤|さとう} {文江|ふみえ}'

// タグを取って文字だけにする
const text = (html: string) => html.replace(/<[^>]+>/g, '')

afterEach(() => i18n.changeLanguage('ja'))

describe('ResidentName（入居者の名前。#389）', () => {
  it('日本語の職員の画面：ふりがな付きで、「さん」を付ける', () => {
    const html = renderToStaticMarkup(<ResidentName name="佐藤 文江" ruby={RUBY} />)

    expect(html).toContain('<ruby>佐藤<rp>(</rp><rt>さとう</rt><rp>)</rp></ruby>')
    expect(html).toContain('<ruby>文江<rp>(</rp><rt>ふみえ</rt><rp>)</rp></ruby>')
    // 「さん」は、名前より少し小さく出す
    expect(html).toContain('<span class="text-[0.85em]">さん</span>')
    expect(text(html).endsWith('さん')).toBe(true)
  })

  it('家族の画面（FuriganaContext が false）：ふりがなは出さず、「さん」だけ付ける', () => {
    const html = renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <ResidentName name="佐藤 文江" />
      </FuriganaContext.Provider>,
    )

    expect(text(html)).toBe('佐藤 文江さん')
  })

  it('honorific={false} なら「さん」を付けない（一覧）', () => {
    const html = renderToStaticMarkup(
      <ResidentName name="佐藤 文江" ruby="佐藤 文江" honorific={false} />,
    )

    expect(html).toBe('佐藤 文江')
  })

  it('インドネシア語・英語：ローマ字のまま、「さん」は付けない', async () => {
    await i18n.changeLanguage('en')

    const html = renderToStaticMarkup(<ResidentName name="Sato Fumie" ruby="Sato Fumie" />)

    expect(html).toBe('Sato Fumie')
    expect(html).not.toContain('<span')
  })

  it('名前の { } | は、ふりがなの書き方として解釈せず、全角にして文字のまま出す（FR-017）', () => {
    const html = renderToStaticMarkup(<ResidentName name="田中{花子|はなこ}" />)

    expect(html).not.toContain('<ruby>')
    expect(text(html)).toBe('田中｛花子｜はなこ｝さん')
  })
})

describe('ResidentFamily（「◯◯さんのご家族（続柄）」。#389）', () => {
  const family = (relationship: string | null) =>
    renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <ResidentFamily name="佐藤 文江" relationship={relationship} />
      </FuriganaContext.Provider>,
    )

  it.each([
    ['daughter', '佐藤 文江さんのご家族（娘）'],
    ['son', '佐藤 文江さんのご家族（息子）'],
    ['spouse', '佐藤 文江さんのご家族（配偶者）'],
    ['grandchild', '佐藤 文江さんのご家族（孫）'],
    ['sibling', '佐藤 文江さんのご家族（きょうだい）'],
    ['other', '佐藤 文江さんのご家族（その他）'],
  ])('続柄 %s', (relationship, expected) => {
    expect(text(family(relationship))).toBe(expected)
  })

  it('続柄がないとき・知らないコードのときは、「（続柄）」を省く', () => {
    expect(text(family(null))).toBe('佐藤 文江さんのご家族')
    expect(text(family('cousin'))).toBe('佐藤 文江さんのご家族')
  })

  it('職員の画面（日本語）：名前と「ご家族」「続柄」にふりがなを付ける', () => {
    const html = renderToStaticMarkup(
      <ResidentFamily name="佐藤 文江" ruby={RUBY} relationship="daughter" />,
    )

    expect(html).toContain('<rt>さとう</rt>')
    expect(html).toContain('<rt>かぞく</rt>')
    expect(html).toContain('<rt>むすめ</rt>')
  })

  it('英語：「Family of …」の形にする', async () => {
    await i18n.changeLanguage('en')
    const html = renderToStaticMarkup(
      <ResidentFamily name="Sato Fumie" ruby="Sato Fumie" relationship="daughter" />,
    )

    expect(text(html)).toBe('Family of Sato Fumie (Daughter)')
  })

  it('インドネシア語：「Keluarga …」の形にする', async () => {
    await i18n.changeLanguage('id')
    const html = renderToStaticMarkup(
      <ResidentFamily name="Sato Fumie" ruby="Sato Fumie" relationship="spouse" />,
    )

    expect(text(html)).toBe('Keluarga Sato Fumie (Pasangan)')
  })
})
