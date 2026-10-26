import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/client'
import ja from '../../i18n/ja.json'
import {
  cancelErrorKey,
  sentAtParts,
  statusKeyOf,
  waitingThemeIds,
  type FamilyRequest,
} from './requestsView'

const request = (overrides: Partial<FamilyRequest>): FamilyRequest => ({
  id: 1,
  theme_id: 1,
  theme_code: 'theme.daily_life',
  emoji: '👀',
  status: 'waiting',
  created_at: '2026-10-26T00:30:00Z',
  days_ago: 0,
  overdue: false,
  ...overrides,
})

describe('sentAtParts', () => {
  it('送った日時を、日本時間の月・日・時刻に分ける', () => {
    expect(sentAtParts('2026-10-26T00:30:00Z')).toEqual({ month: '10', day: '26', time: '9:30' })
  })
})

describe('cancelErrorKey', () => {
  it('返事がついたあとの取り消し（already_replied）は、家族向けの専用の文言にする', () => {
    const error = new ApiError(409, 'already_replied', 'error.already_replied')
    expect(cancelErrorKey(error)).toBe('requests.cancel_after_reply')
  })

  it('ほかのエラーは、API が返した文言のキーのまま', () => {
    const error = new ApiError(404, 'not_found', 'error.not_found')
    expect(cancelErrorKey(error)).toBe('error.not_found')
  })

  it('API のエラーでないものは、server_error の文言にする', () => {
    expect(cancelErrorKey(new Error('x'))).toBe('error.server_error')
  })
})

describe('waitingThemeIds', () => {
  it('返事待ちのテーマだけを集める（返事済み・取り消し済みは、もう一度頼める）', () => {
    const ids = waitingThemeIds([
      request({ id: 1, theme_id: 1, status: 'waiting' }),
      request({ id: 2, theme_id: 2, status: 'answered' }),
      request({ id: 3, theme_id: 3, status: 'cancelled' }),
    ])
    expect([...ids]).toEqual([1])
  })
})

describe('statusKeyOf', () => {
  it('状態ごとの文言のキーを返す', () => {
    expect(statusKeyOf(request({ status: 'waiting' }))).toBe('requests.status_waiting')
    expect(statusKeyOf(request({ status: 'answered' }))).toBe('requests.status_answered')
    expect(statusKeyOf(request({ status: 'cancelled' }))).toBe('requests.status_cancelled')
  })
})

describe('辞書', () => {
  it('画面が使う文言が、すべて ja.json にある', () => {
    const requests: Record<string, string> = ja.requests
    for (const key of [
      'cancel_after_reply',
      'status_waiting',
      'status_answered',
      'status_cancelled',
      'overdue',
      'days_ago',
      'days_ago_zero',
      'sent_at',
    ]) {
      expect(requests[key], key).toBeTruthy()
    }
  })

  it('初期データの 8 つのテーマすべてに、名前がある', () => {
    expect(Object.keys(ja.theme)).toHaveLength(8)
  })
})
