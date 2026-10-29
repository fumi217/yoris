import { describe, expect, it } from 'vitest'
import en from './en.json'
import i18n, { SUPPORTED_LANGUAGES, isLanguage } from './index'
import id from './id.json'
import ja from './ja.json'

// {a: {b: 'x'}} → {'a.b': 'x'}
function flatten(object: Record<string, unknown>, prefix = ''): Record<string, string> {
  return Object.entries(object).reduce<Record<string, string>>((result, [key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof value === 'string') return { ...result, [path]: value }
    return { ...result, ...flatten(value as Record<string, unknown>, path) }
  }, {})
}

const jaKeys = flatten(ja)

describe('表示言語の辞書（spec 001 の T082・T084・T085）', () => {
  it('日本語・インドネシア語・英語を選べる（FR-021）', () => {
    expect(SUPPORTED_LANGUAGES).toEqual(['ja', 'id', 'en'])
    expect(isLanguage('id')).toBe(true)
    expect(isLanguage('fr')).toBe(false)
    expect(isLanguage('')).toBe(false)
  })

  it('言語を切り替えると、辞書の文言が変わる', async () => {
    try {
      await i18n.changeLanguage('en')
      expect(i18n.t('auth.logout')).toBe('Log out')
      await i18n.changeLanguage('id')
      expect(i18n.t('auth.logout')).toBe('Keluar')
    } finally {
      await i18n.changeLanguage('ja')
    }
    expect(i18n.t('auth.logout')).toBe('ログアウト')
  })

  it('インドネシア語・英語の辞書にだけあるキー（書き間違い）はない', () => {
    for (const [name, dictionary] of [
      ['id', id],
      ['en', en],
    ] as const) {
      const extra = Object.keys(flatten(dictionary)).filter((key) => !(key in jaKeys))
      expect(extra, `${name}.json にだけあるキー`).toEqual([])
    }
  })

  it('インドネシア語・英語には、ふりがなの書き方 {漢字|かんじ} を使わない', () => {
    for (const [name, dictionary] of [
      ['id', id],
      ['en', en],
    ] as const) {
      const withRuby = Object.entries(flatten(dictionary)).filter(([, text]) =>
        /\{[^}]*\|/.test(text),
      )
      expect(withRuby, `${name}.json でふりがなを使っている文言`).toEqual([])
    }
  })

  it('訳したグループは、日本語と同じキーがそろっている（一部だけ訳して止めない）', () => {
    for (const [name, dictionary] of [
      ['id', id],
      ['en', en],
    ] as const) {
      const translated = flatten(dictionary)
      const groups = new Set(Object.keys(dictionary))
      const missing = Object.keys(jaKeys).filter(
        (key) => groups.has(key.split('.')[0]) && !(key in translated),
      )
      expect(missing, `${name}.json に足りないキー`).toEqual([])
    }
  })

  it('訳さないグループは、申し込みの画面と開発用だけ（新しいグループの訳し忘れを止める）', () => {
    // 申し込みの画面はログイン前、dev は開発のときだけで、言語を選べない
    const notTranslated = ['signup', 'signup_complete', 'steps', 'dev']
    for (const [name, dictionary] of [
      ['id', id],
      ['en', en],
    ] as const) {
      const missing = Object.keys(ja).filter(
        (group) => !(group in dictionary) && !notTranslated.includes(group),
      )
      expect(missing, `${name}.json にないグループ`).toEqual([])
    }
  })

  it('値に入れる {{month}} などは、訳でも日本語と同じものを残す', () => {
    const placeholders = (text: string) => (text.match(/\{\{\w+\}\}/g) ?? []).sort()
    for (const [name, dictionary] of [
      ['id', id],
      ['en', en],
    ] as const) {
      const different = Object.entries(flatten(dictionary)).filter(
        ([key, text]) =>
          JSON.stringify(placeholders(text)) !== JSON.stringify(placeholders(jaKeys[key])),
      )
      expect(
        different.map(([key]) => key),
        `${name}.json で {{ }} が違うキー`,
      ).toEqual([])
    }
  })
})
