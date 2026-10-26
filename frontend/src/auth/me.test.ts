import { describe, expect, it } from 'vitest'
import { canOpen, homePathFor, type Me, type StaffRole } from './me'

const family: Me = { kind: 'family', role: null, display_name: 'テストさんの母', language: 'ja' }
const staff = (role: StaffRole): Me => ({
  kind: 'staff',
  role,
  display_name: 'テスト職員',
  language: 'ja',
})

describe('homePathFor', () => {
  it.each([
    [null, '/login'],
    [family, '/family'],
    [staff('care_worker'), '/staff'],
    [staff('leader'), '/staff'],
    [staff('counselor'), '/staff'],
    [staff('director'), '/staff'],
    [staff('clerk'), '/admin'],
  ])('%o は %s から始める', (me, path) => {
    expect(homePathFor(me)).toBe(path)
  })
})

describe('canOpen', () => {
  it('家族は、職員の画面と管理画面を開けない', () => {
    expect(canOpen(family, 'family')).toBe(true)
    expect(canOpen(family, 'staff')).toBe(false)
    expect(canOpen(family, 'admin')).toBe(false)
  })

  it('事務員は、職員の画面を開けない', () => {
    expect(canOpen(staff('clerk'), 'staff')).toBe(false)
    expect(canOpen(staff('clerk'), 'admin')).toBe(true)
  })

  it('介護職員・リーダーは、管理画面を開けない', () => {
    expect(canOpen(staff('care_worker'), 'admin')).toBe(false)
    expect(canOpen(staff('leader'), 'admin')).toBe(false)
  })

  it('生活相談員・施設長は、職員の画面と管理画面の両方を開ける', () => {
    for (const role of ['counselor', 'director'] as const) {
      expect(canOpen(staff(role), 'staff')).toBe(true)
      expect(canOpen(staff(role), 'admin')).toBe(true)
    }
  })

  it('職員は、家族の画面を開けない', () => {
    expect(canOpen(staff('director'), 'family')).toBe(false)
  })
})
