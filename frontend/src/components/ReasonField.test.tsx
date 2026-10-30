import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import en from '../i18n/en.json'
import id from '../i18n/id.json'
import { ReasonField } from './ReasonField'

// ふりがな（ルビ）とタグを取って、画面に読める文字だけにする
const plain = (html: string) => html.replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>|<[^>]+>/g, '')

const render = (props: Partial<Parameters<typeof ReasonField>[0]> = {}) =>
  renderToStaticMarkup(
    <ReasonField
      value="家族に伝える理由"
      onChange={() => {}}
      tooLong={false}
      locked={false}
      {...props}
    />,
  )

describe('ReasonField', () => {
  it('普段は、直せる欄と「理由を書いてから、ボタンを押してください」の案内を出す', () => {
    const html = render()

    expect(html).not.toMatch(/readonly/i)
    expect(plain(html)).toContain('理由を書いてから、ボタンを押してください')
    expect(plain(html)).not.toContain('やめる')
  })

  it('確かめの状態のあいだは、欄を読み取り専用にして、直すときは「やめる」と案内する', () => {
    const html = render({ locked: true })

    expect(html).toMatch(/<textarea[^>]*readonly=""/i)
    expect(plain(html)).toContain('この理由で取り消します。直すときは「やめる」を押してください')
    expect(plain(html)).not.toContain('理由を書いてから')
  })

  it('読み取り専用でも disabled にしない（キーボードで行けて、読み上げで読めるように）', () => {
    for (const locked of [false, true]) {
      expect(render({ locked })).not.toMatch(/<textarea[^>]*disabled/)
    }
  })

  it('読み取り専用の欄は、灰色にする', () => {
    expect(render({ locked: true })).toMatch(/<textarea[^>]*class="[^"]*read-only:bg-gray-100/)
  })

  it('入力欄の枠は、3:1 以上の濃さにする（border-ink-sub。白との比 4.83。1.4.11）', () => {
    expect(render()).toMatch(/<textarea[^>]*class="[^"]*border-ink-sub/)
    expect(render()).not.toMatch(/<textarea[^>]*class="[^"]*border-field-line/)
  })

  it.each([
    ['en', en.layout.confirm_stop],
    ['id', id.layout.confirm_stop],
  ])(
    '%s では、案内の中の「やめる」が、その言語のボタンの文字と同じ（取り消しのボタンと取り違えない）',
    async (language, stop) => {
      try {
        await i18n.changeLanguage(language)
        const html = plain(render({ locked: true }))

        // 静的な描画では、文の中の引用符は &quot; になる
        expect(html).toContain(`&quot;${stop}&quot;`)
        expect(html).not.toContain('{{stop}}')
        expect(html).not.toContain('やめる')
      } finally {
        await i18n.changeLanguage('ja')
      }
    },
  )

  it('案内は読み上げに伝わるようにして、欄とつなぐ', () => {
    const html = render()

    const guideId = html.match(/<p id="([^"]+)" aria-live="polite"/)?.[1]
    expect(guideId).toBeTruthy()
    expect(html).toContain(`aria-describedby="${guideId}"`)
  })

  it('入れた理由は、辞書を通さず、そのまま欄に入れる', () => {
    expect(render({ value: '<b>急な工事</b>' })).toContain('&lt;b&gt;急な工事&lt;/b&gt;')
  })

  it('長すぎるときだけ、赤い印と案内を出す', () => {
    expect(render()).toContain('aria-invalid="false"')
    expect(plain(render())).not.toContain('200 文字までで書いてください')

    const html = render({ tooLong: true })
    expect(html).toContain('aria-invalid="true"')
    expect(plain(html)).toContain('200 文字までで書いてください')
  })
})
