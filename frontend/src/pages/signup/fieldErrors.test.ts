import { describe, expect, it } from 'vitest'
import { FIELD_ORDER, placeServerError, validateSignup } from './fieldErrors'

describe('placeServerError', () => {
  it('メールアドレスの不一致は、確認用の欄に出す', () => {
    expect(placeServerError('error.email_mismatch')).toEqual({
      field: 'email_confirm',
      key: 'error.email_mismatch',
    })
  })

  it('入力の間違い（422）は、パスワードの欄に、よく使われるパスワードの文言で出す', () => {
    expect(placeServerError('error.validation_error')).toEqual({
      field: 'password',
      key: 'signup.password_common',
    })
  })

  it('欄が決まらないものは、フォーム全体のエラーにする', () => {
    expect(placeServerError('error.payment_service_unavailable')).toEqual({
      field: null,
      key: 'error.payment_service_unavailable',
    })
    expect(placeServerError('error.not_found').field).toBeNull()
  })
})

const valid = {
  facility_name: 'さくら苑',
  director_name: '架空 太郎',
  email: 'director@example.test',
  email_confirm: 'director@example.test',
  password: 'garden-lantern-42',
}

describe('validateSignup', () => {
  it('施設名・施設長の名前が 100 文字を超えていたら、その欄に出す（サーバーの上限と同じ）', () => {
    const errors = validateSignup({
      ...valid,
      facility_name: 'あ'.repeat(101),
      director_name: 'あ'.repeat(100),
    })

    expect(errors).toEqual({ facility_name: 'signup.error_too_long' })
  })

  it('名前の長さは、文字数で数える（𠮷 のような文字も 1 文字）', () => {
    expect(
      validateSignup({
        ...valid,
        facility_name: '𠮷'.repeat(100),
        director_name: '𠮷'.repeat(101),
      }),
    ).toEqual({ director_name: 'signup.error_too_long' })
  })

  it('全部そろっていれば、エラーはない', () => {
    expect(validateSignup(valid)).toEqual({})
  })

  it('空の欄は、すべて「入力してください」にする（空白だけも同じ）', () => {
    const errors = validateSignup({
      facility_name: '',
      director_name: '   ',
      email: '',
      email_confirm: '',
      password: '',
    })

    expect(Object.keys(errors).sort()).toEqual([...FIELD_ORDER].sort())
    expect(Object.values(errors).every((key) => key === 'signup.error_required')).toBe(true)
  })

  it('メールアドレスの形式がおかしいときは、その欄に出す（ドットなしの test@test も）', () => {
    expect(validateSignup({ ...valid, email: 'test@test', email_confirm: 'test@test' }).email).toBe(
      'signup.email_invalid',
    )
    expect(
      validateSignup({ ...valid, email: 'no-at-mark', email_confirm: 'no-at-mark' }).email,
    ).toBe('signup.email_invalid')
  })

  it('メールアドレスが 2 回で違うときは、確認用の欄に出す（前後の空白は無視する）', () => {
    expect(validateSignup({ ...valid, email_confirm: 'other@example.test' }).email_confirm).toBe(
      'error.email_mismatch',
    )
    expect(validateSignup({ ...valid, email_confirm: ' director@example.test ' })).toEqual({})
  })

  it('1 つめのメールアドレスの形式がおかしいときは、不一致を重ねて出さない', () => {
    const errors = validateSignup({ ...valid, email: 'test@test', email_confirm: 'tetse@test' })

    expect(errors.email).toBe('signup.email_invalid')
    expect(errors.email_confirm).toBeUndefined()
  })

  it('間違いのある欄すべてに、一度に出す', () => {
    const errors = validateSignup({
      ...valid,
      email_confirm: 'other@example.test',
      password: 'abc',
    })

    expect(errors).toEqual({
      email_confirm: 'error.email_mismatch',
      password: 'signup.password_invalid',
    })
  })
})
