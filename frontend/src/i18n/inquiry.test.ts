import { describe, expect, it } from 'vitest'
import i18n from './index'
import ja from './ja.json'
import { stripRuby } from './rubyText'

// ふりがな（{漢字|かんじ}）を外して、画面に出る文字で比べる
const text = (key: string, options?: Record<string, string>) => stripRuby(i18n.t(key, options))

describe('問い合わせ AI の文言（spec 004 の T012）', () => {
  it('質問の種類のすべてに名前がある（backend/app/models/inquiry.py の CATEGORIES）', () => {
    expect(Object.keys(ja.inquiry.category).sort()).toEqual(
      ['care_request', 'complaint', 'medical', 'money', 'other', 'urgent'].sort(),
    )
  })

  it('AI の答えであることと、職員に伝えることを、家族の画面に出せる（FR-005・FR-012a）', () => {
    expect(text('inquiry.ai_notice')).toBe(
      'AI がお答えしています。記録にないことはお答えできません',
    )
    expect(text('inquiry.handoff_notice')).toContain('施設の職員にこの会話の一部をお伝えします')
  })

  it('職員の返事は「◯◯からの返事」と区別して出す（FR-005。名前は返事をした職員の表示名）', () => {
    expect(text('inquiry.reply_from', { name: '山本' })).toBe('山本からの返事')
  })
})
