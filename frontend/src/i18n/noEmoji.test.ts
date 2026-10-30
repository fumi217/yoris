import { describe, expect, it } from 'vitest'
import en from './en.json'
import id from './id.json'
import ja from './ja.json'

// 画面に絵文字を出さない（アイコンは Font Awesome にそろえる。デザインの決めごと 14 章。#388）。
// ✔ ✓ ◀ ▶ ➤ のような記号も、アイコンにする。コメントの中は対象外（「→」などを説明に使うため）。

const EMOJI = /[\p{Extended_Pictographic}✓✔➤◀▶]/u

const sources = import.meta.glob('/src/**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

/** コメントを除いた、動くコードの行だけにする（行の終わりのコメントも外す）。 */
function codeLines(source: string): { line: number; text: string }[] {
  const lines: { line: number; text: string }[] = []
  let inBlock = false
  source.split('\n').forEach((raw, index) => {
    let text = raw
    if (inBlock) {
      if (text.includes('*/')) {
        inBlock = false
        text = text.slice(text.indexOf('*/') + 2)
      } else {
        return
      }
    }
    // 行の終わりのコメント（空白のあとの //）を外す。'http://…' の // は、前に空白がないので、外さない。
    // 文字列の中に「 // 」（前に空白がある）があると、その後ろは見ない（見逃すだけで、誤って落ちることはない）
    text = text.replace(/\/\*.*?\*\//g, '').replace(/\s\/\/.*$/, '')
    if (text.includes('/*')) {
      inBlock = true
      text = text.slice(0, text.indexOf('/*'))
    }
    if (text.trim().startsWith('//')) return
    if (text.trim()) lines.push({ line: index + 1, text })
  })
  return lines
}

describe('絵文字を出さない（#388）', () => {
  it('画面のコード（テスト以外）に、絵文字・記号の ✔ ✓ ◀ ▶ ➤ がない', () => {
    const found: string[] = []
    for (const [path, source] of Object.entries(sources)) {
      if (path.includes('.test.')) continue
      for (const { line, text } of codeLines(source)) {
        if (EMOJI.test(text))
          found.push(`${path.replace('/src/', '')}:${line}  ${text.trim().slice(0, 60)}`)
      }
    }

    expect(found, '絵文字が残っているところ（Icon を使う）').toEqual([])
  })

  it.each([
    ['日本語', ja],
    ['英語', en],
    ['インドネシア語', id],
  ])('%s の辞書に、絵文字・記号がない', (_name, dictionary) => {
    const found: string[] = []
    const walk = (node: unknown, path: string) => {
      if (typeof node === 'string') {
        if (EMOJI.test(node)) found.push(`${path}: ${node.slice(0, 40)}`)
      } else if (node && typeof node === 'object') {
        for (const [key, value] of Object.entries(node)) walk(value, path ? `${path}.${key}` : key)
      }
    }
    walk(dictionary, '')

    expect(found, '絵文字が残っているキー（画面の側で Icon を使う）').toEqual([])
  })
})
