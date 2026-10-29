import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import { Logo } from './Logo'

describe('Logo', () => {
  it('YORIS のロゴを、読み上げの名前（alt）つきで出す（1.1.1）', () => {
    const html = renderToStaticMarkup(<Logo />)

    expect(html).toContain('<img')
    expect(html).toContain('alt="YORIS"')
  })

  it('画像の大きさ（475×122）を書いて、読み込み中に表示がずれないようにする。縦横比は変えない', () => {
    const html = renderToStaticMarkup(<Logo />)

    expect(html).toContain('width="475"')
    expect(html).toContain('height="122"')
    // 高さだけを決めて、幅は自動（縦横比のまま）。狭い枠でも、つぶれない
    expect(html).toMatch(/class="[^"]*w-auto/)
    expect(html).toMatch(/class="[^"]*shrink-0/)
    // img の max-width:100% を外す（外さないと、狭い枠で幅だけ縮んで縦横比が崩れる。#331）
    expect(html).toMatch(/class="[^"]*max-w-none/)
  })

  it('高さは、置く場所で決める：家族は 28px（h-7）、職員・管理画面は 32px（h-8）', () => {
    expect(renderToStaticMarkup(<Logo />)).toMatch(/class="[^"]*h-7/)
    expect(renderToStaticMarkup(<Logo className="h-8" />)).toMatch(/class="[^"]*h-8/)
  })

  it('どの言語でも、読み上げの名前は YORIS（アプリの名前は、翻訳しない）', async () => {
    try {
      for (const language of ['ja', 'en', 'id']) {
        await i18n.changeLanguage(language)
        expect(renderToStaticMarkup(<Logo />)).toContain('alt="YORIS"')
      }
    } finally {
      await i18n.changeLanguage('ja')
    }
  })
})
