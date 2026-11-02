import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import i18n from '../../i18n'
import { Mascot } from './Mascot'
import {
  BUBBLE_DELAY_MS,
  BUBBLE_KEYS,
  BUBBLE_SHOW_MS,
  GO_DELAY_MS,
  hasSeenBubble,
  INQUIRY_PATH,
  isPlainClick,
  markBubbleSeen,
  pickBubbleKey,
} from './mascotLogic'

const render = () =>
  renderToStaticMarkup(
    <MemoryRouter>
      <Mascot />
    </MemoryRouter>,
  )

describe('Mascot', () => {
  it('お問い合わせへのリンクで、名前は「お問い合わせ（AI に質問する）」', () => {
    const html = render()

    expect(html).toMatch(/<a [^>]*href="\/family\/inquiry"/)
    expect(html).toContain('aria-label="お問い合わせ（AI に質問する）"')
  })

  it('絵は飾り（alt が空）。2 枚とも、大きさ（308×263）を書いて、同じ場所に重ねる', () => {
    const html = render()
    const images = html.match(/<img[^>]*>/g) ?? []

    expect(images).toHaveLength(2)
    for (const image of images) {
      expect(image).toContain('alt=""')
      expect(image).toContain('width="308"')
      expect(image).toContain('height="263"')
      expect(image).toMatch(/class="[^"]*col-start-1 row-start-1/)
      expect(image).toMatch(/class="[^"]*drop-shadow/)
    }
  })

  it('はじめは、ふつうの顔だけが見える（嬉しい顔は、読み込んでおいて、透明にする）', () => {
    const [normal, happy] = renderToStaticMarkup(
      <MemoryRouter>
        <Mascot />
      </MemoryRouter>,
    ).match(/<img[^>]*>/g) ?? ['', '']

    expect(normal).not.toContain('opacity-0')
    expect(happy).toContain('opacity-0')
  })

  it('外側の枠（リンク）は動かさず、中の絵（mascot-float）だけを動かす', () => {
    const html = render()

    expect(html).toMatch(/<a [^>]*>\s*<span class="mascot-float/)
  })

  it('右下に固定して、幅 320px 以下・高さが低いときは固定をやめる。メニューの上に置く', () => {
    const html = render()

    expect(html).toContain('fixed')
    expect(html).toContain('bottom-[calc(var(--family-menu-height)+1rem)]')
    expect(html).toContain('[@media(max-width:320px)]:static')
    expect(html).toContain('[@media(max-height:400px)]:static')
    expect(html).toContain('justify-end')
  })

  it('押す大きさは 44px 以上（幅 72px・高さは縦横比から約 61px）', () => {
    expect(render()).toContain('w-[72px]')
    expect(Math.round((72 * 263) / 308)).toBeGreaterThanOrEqual(44)
  })

  it('どの言語でも、リンクに名前がある', async () => {
    try {
      for (const language of ['ja', 'en', 'id']) {
        await i18n.changeLanguage(language)
        expect(render()).toMatch(/aria-label="[^"]+"/)
      }
    } finally {
      await i18n.changeLanguage('ja')
    }
  })
})

describe('mascotLogic', () => {
  it('行き先は、お問い合わせ。嬉しい顔は 0.4 秒見せる', () => {
    expect(INQUIRY_PATH).toBe('/family/inquiry')
    expect(GO_DELAY_MS).toBe(400)
  })

  const click = { button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false }

  it('ふつうの左クリックだけ、待ってから移る', () => {
    expect(isPlainClick(click)).toBe(true)
  })

  it.each([
    ['右クリック', { button: 2 }],
    ['真ん中のボタン', { button: 1 }],
    ['Ctrl＋クリック', { ctrlKey: true }],
    ['Cmd＋クリック', { metaKey: true }],
    ['Shift＋クリック', { shiftKey: true }],
    ['Alt＋クリック', { altKey: true }],
  ])('%s は、待たずにブラウザの動きに任せる', (_name, change) => {
    expect(isPlainClick({ ...click, ...change })).toBe(false)
  })
})

describe('押せると分かるようにする（#405）', () => {
  const withBubble = (key: string) =>
    renderToStaticMarkup(
      <MemoryRouter>
        <Mascot initialBubbleKey={key} />
      </MemoryRouter>,
    )
  // ふりがな（<rt>・<rp>）を除いた、画面に出る文字
  const text = (html: string) =>
    html.replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '').replace(/<[^>]+>/g, '')

  it('はじめは、吹き出しを出さない（開いてから 0.8 秒あとに出す）', () => {
    expect(render()).not.toContain('data-mascot-bubble')
    expect(BUBBLE_DELAY_MS).toBe(800)
  })

  it('吹き出しは、3 つの文のどれか。飾り（読み上げない）で、押せない', () => {
    for (const [key, shown] of [
      ['layout.mascot_bubble_1', '聞いてみませんか？'],
      ['layout.mascot_bubble_2', '知りたいこと、ありませんか？'],
      ['layout.mascot_bubble_3', '気になること、聞けます'],
    ]) {
      const html = withBubble(key)

      expect(text(html)).toContain(shown)
      expect(html).toMatch(/<div aria-hidden="true" data-mascot-bubble/)
    }
    // 押せるのは、ヨリィくんのリンクだけ。吹き出しは、リンクの外
    const html = withBubble('layout.mascot_bubble_1')
    expect(html.match(/<a /g)).toHaveLength(1)
    expect(html.indexOf('data-mascot-bubble')).toBeLessThan(html.indexOf('<a '))
    // リンクの名前は、吹き出しがあっても、同じ
    expect(html).toContain('aria-label="お問い合わせ（AI に質問する）"')
  })

  it('吹き出しの文は、辞書にある（日本語・英語・インドネシア語）', () => {
    for (const language of ['ja', 'en', 'id']) {
      for (const key of BUBBLE_KEYS) {
        expect(i18n.getResource(language, 'translation', key)).toBeTruthy()
      }
    }
  })

  it('文は、乱数で選ぶ（0 以上 1 未満を、3 つに分ける）', () => {
    expect(pickBubbleKey(0)).toBe('layout.mascot_bubble_1')
    expect(pickBubbleKey(0.34)).toBe('layout.mascot_bubble_2')
    expect(pickBubbleKey(0.99)).toBe('layout.mascot_bubble_3')
    // 範囲の外が来ても、落ちない
    expect(pickBubbleKey(1)).toBe('layout.mascot_bubble_3')
  })

  it('出す時間は 5 秒（2.2.2）。タブの記憶が使えなくても、落ちない（出す扱い）', () => {
    expect(BUBBLE_SHOW_MS).toBe(5000)
    expect(hasSeenBubble()).toBe(false)
    expect(() => markBubbleSeen()).not.toThrow()
  })

  it('影を濃く大きくして、背景から目立たせる', () => {
    const images = render().match(/<img[^>]*>/g) ?? []

    for (const image of images) {
      expect(image).toContain('drop-shadow-[0_4px_8px_rgba(15,31,61,0.45)]')
    }
  })
})
