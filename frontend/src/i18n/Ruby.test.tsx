import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import i18n from './index'
import { FuriganaContext } from './furigana'
import { Ruby } from './Ruby'
import { parseRuby, stripRuby } from './rubyText'

describe('parseRuby', () => {
  it('ふりがなの書き方を、文とふりがなの部分に分ける', () => {
    expect(parseRuby('{全部|ぜんぶ}（8{割|わり}）')).toEqual([
      { kind: 'ruby', base: '全部', reading: 'ぜんぶ' },
      { kind: 'text', text: '（8' },
      { kind: 'ruby', base: '割', reading: 'わり' },
      { kind: 'text', text: '）' },
    ])
  })

  it('書き方を使わない文（インドネシア語・英語）は、そのまま 1 つの文になる', () => {
    expect(parseRuby('Makan siang habis')).toEqual([{ kind: 'text', text: 'Makan siang habis' }])
  })

  it('書き方に合わない { } は、そのまま文として残す', () => {
    expect(parseRuby('{だけ} と {|よみ}')).toEqual([{ kind: 'text', text: '{だけ} と {|よみ}' }])
  })
})

describe('stripRuby', () => {
  it('ふりがなを外して漢字だけにする', () => {
    expect(stripRuby('{全部|ぜんぶ}（8{割|わり}）')).toBe('全部（8割）')
  })
})

describe('Ruby', () => {
  it('ふりがなを <ruby> にして出す', () => {
    expect(renderToStaticMarkup(<Ruby text="{全部|ぜんぶ}たべた" />)).toBe(
      '<ruby>全部<rp>(</rp><rt>ぜんぶ</rt><rp>)</rp></ruby>たべた',
    )
  })

  it('文は HTML として解釈せず、文字として出す', () => {
    expect(renderToStaticMarkup(<Ruby text="<script>x</script>" />)).toBe(
      '&lt;script&gt;x&lt;/script&gt;',
    )
  })
})

describe('辞書', () => {
  // エラーのコードの足し忘れは backend/tests/unit/test_errors.py（#181）で確かめる
  it('初めは日本語で、辞書から文言を引ける', () => {
    expect(i18n.language).toBe('ja')
    expect(i18n.t('error.already_replied')).toBe('ほかの{職員|しょくいん}が{返事|へんじ}をしました')
  })
})

describe('家族の画面のふりがな（#260）', () => {
  it('FuriganaContext が false のときは、ふりがなを外して漢字だけにする', () => {
    const html = renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <Ruby text="{全部|ぜんぶ}（8{割|わり}）" />
      </FuriganaContext.Provider>,
    )

    expect(html).toBe('全部（8割）')
  })

  it('ふりがなを外しても、文は HTML として解釈しない', () => {
    const html = renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <Ruby text="<b>{太字|ふとじ}</b>" />
      </FuriganaContext.Provider>,
    )

    expect(html).toBe('&lt;b&gt;太字&lt;/b&gt;')
  })

  it('初期値（職員の画面・管理画面）は、ふりがなを出す', () => {
    expect(renderToStaticMarkup(<Ruby text="{全部|ぜんぶ}" />)).toContain('<ruby>')
  })
})
