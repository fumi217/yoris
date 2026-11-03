import { describe, expect, it } from 'vitest'
import { staffTabs } from './staffTabs'

const counts = { messages: 3, approvals: 2 }

describe('職員の画面のタブ（#437）', () => {
  it('介護職員：入居者一覧・家族からのメッセージ・面会予定の 3 つ（承認は出さない）', () => {
    expect(staffTabs('care_worker', counts).map((tab) => tab.to)).toEqual([
      '/staff',
      '/staff/messages',
      '/staff/visits/today',
    ])
  })

  it('リーダー・施設長には、様子のメモの承認も出す', () => {
    for (const role of ['leader', 'director'] as const) {
      expect(staffTabs(role, counts).map((tab) => tab.to)).toContain('/staff/memo-approvals')
    }
    expect(staffTabs('counselor', counts).map((tab) => tab.to)).not.toContain(
      '/staff/memo-approvals',
    )
  })

  it('件数は、メッセージと承認のタブにだけ添える', () => {
    const tabs = staffTabs('leader', counts)

    expect(tabs.map((tab) => tab.count)).toEqual([undefined, 3, undefined, 2])
  })

  it('入居者の詳細の画面でも、入居者一覧のタブが選ばれる', () => {
    const [residents] = staffTabs('leader', counts)

    expect(residents.isActive('/staff')).toBe(true)
    expect(residents.isActive('/staff/residents/7')).toBe(true)
    expect(residents.isActive('/staff/residents/7/contact-book')).toBe(true)
    expect(residents.isActive('/staff/messages')).toBe(false)
  })

  it('面会の予約の一覧でも、面会予定のタブが選ばれる', () => {
    const visits = staffTabs('leader', counts)[2]

    expect(visits.isActive('/staff/visits')).toBe(true)
    expect(visits.isActive('/staff/visits/today')).toBe(true)
  })
})
