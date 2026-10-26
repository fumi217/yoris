import { describe, expect, it } from 'vitest'
import i18n from './index'
import { stripRuby } from './rubyText'

const memo = (key: string) => stripRuby(i18n.t(`memo.${key}`))

describe('様子のメモの文言（spec 007 の T006）', () => {
  it('書く画面と承認の画面の案内がある（FR-016）', () => {
    expect(memo('call_if_urgent')).toBe('急変・事故は、すぐに電話で連絡してください')
    expect(memo('check_other_names')).toBe('ほかの入居者の名前が入っていないか確かめてください')
    expect(memo('check_medical')).toBe('医療・服薬・体調の判断が入っていないか確かめてください')
  })

  it('家族の連絡帳で、AI で整えた文であることを示せる（FR-012）', () => {
    expect(memo('ai_notice')).toBe('職員が書いた内容を、AI で読みやすい日本語に整えています')
  })

  it('ボタンと、AI が止まったときの案内がある（FR-003・FR-020）', () => {
    expect(memo('to_japanese')).toBe('日本語にする')
    expect(memo('tidy')).toBe('整える')
    expect(memo('confirm')).toBe('確かめました')
    expect(memo('unavailable')).toBe('いま日本語にできません。時間をおいてもう一度お試しください')
  })
})
