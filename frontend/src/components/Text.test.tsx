import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { FamilyContext } from '../i18n/audience'
import { FuriganaContext } from '../i18n/furigana'
import i18n from '../i18n/index'
import { Text } from './Text'

describe('Text', () => {
  it('職員・ログイン・申し込みでは、validation_error をそのまま出す', () => {
    expect(renderToStaticMarkup(<Text k="error.validation_error" />)).toContain(
      '<rt>にゅうりょく</rt>',
    )
  })

  it('家族の画面では、validation_error を「もう一度、やり直してください」にする', () => {
    const html = renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <FamilyContext.Provider value={true}>
          <Text k="error.validation_error" />
        </FamilyContext.Provider>
      </FuriganaContext.Provider>,
    )
    expect(html).toContain('もう一度、やり直してください')
    expect(html).not.toContain('確かめてください')
  })

  it('今の言語の辞書に家族用の言い方がなければ、日本語の家族用ではなく、ふつうのキーを出す', async () => {
    // 日本語へ戻る設定（fallbackLng）のせいで、ほかの言語の家族の画面に日本語の文が出ないように
    await i18n.changeLanguage('en')
    try {
      const html = renderToStaticMarkup(
        <FamilyContext.Provider value={true}>
          <Text k="error.validation_error" />
        </FamilyContext.Provider>,
      )
      expect(html).not.toContain('もう一度、やり直してください')
    } finally {
      await i18n.changeLanguage('ja')
    }
  })

  it('家族用の言い方がないキーは、家族の画面でもそのまま出す', () => {
    const html = renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <FamilyContext.Provider value={true}>
          <Text k="error.forbidden" />
        </FamilyContext.Provider>
      </FuriganaContext.Provider>,
    )
    expect(html).toContain('このページは表示できません')
  })
})
