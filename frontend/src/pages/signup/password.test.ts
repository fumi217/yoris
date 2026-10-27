import { describe, expect, it } from 'vitest'
import { isValidPassword } from './password'

describe('isValidPassword', () => {
  it('半角の英数字と記号で、8〜64 文字なら通す', () => {
    expect(isValidPassword('abcd1234')).toBe(true)
    expect(isValidPassword('a'.repeat(64))).toBe(true)
    expect(isValidPassword('pass word!')).toBe(true) // 空白も使える
  })

  it('短い・長いものは通さない', () => {
    expect(isValidPassword('abc1234')).toBe(false) // 7 文字
    expect(isValidPassword('a'.repeat(65))).toBe(false)
    expect(isValidPassword('')).toBe(false)
  })

  it('全角・かなは通さない', () => {
    expect(isValidPassword('ｐａｓｓｗｏｒｄ１２３')).toBe(false)
    expect(isValidPassword('ぱすわーど12345678')).toBe(false)
  })
})
