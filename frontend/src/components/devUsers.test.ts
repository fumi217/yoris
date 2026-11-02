import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import { devUserLabel, type DevUser } from './devUsers'

// 本物の辞書（ja.json）で確かめる
const t = i18n.t.bind(i18n) as (key: string, options?: Record<string, string>) => string

describe('devUserLabel', () => {
  it('職員は「名前／役割」。ふりがなは外す', () => {
    const user: DevUser = {
      user_id: 1,
      kind: 'staff',
      role: 'care_worker',
      display_name: '田中',
      language: 'ja',
    }
    expect(devUserLabel(user, t)).toBe('田中／介護職員')
  })

  it('日本語でない職員は、言語も付ける', () => {
    const user: DevUser = {
      user_id: 2,
      kind: 'staff',
      role: 'care_worker',
      display_name: 'シティ',
      language: 'id',
    }
    expect(devUserLabel(user, t)).toBe('シティ／介護職員（id）')
  })

  it('言語が分からないときは、言語を付けない', () => {
    const user = {
      user_id: 3,
      kind: 'staff',
      role: 'care_worker',
      display_name: '田中',
    } as DevUser
    expect(devUserLabel(user, t)).toBe('田中／介護職員')
  })

  it('家族は、入居者の呼び名だけ', () => {
    const user: DevUser = {
      user_id: 17,
      kind: 'family',
      role: null,
      display_name: '佐藤 文江',
      language: 'ja',
    }
    expect(devUserLabel(user, t)).toBe('佐藤 文江')
  })
})
