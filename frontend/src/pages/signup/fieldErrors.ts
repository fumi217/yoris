// 申し込みのエラーを、どの入力欄に出すか決める。エラーは、その欄のすぐ近くに出す
// （画面の下のほうだけに出すと、どこが間違いか分かりにくいため）。
// 確認は、送る前に全部の欄をまとめて行い、間違いのある欄すべてに一度に出す
// （デジタル庁の入力欄の決まり：エラーは送信ボタンを押したときに出す）。

import { isValidPassword } from './password'

export type FieldName = 'facility_name' | 'director_name' | 'email' | 'email_confirm' | 'password'

// 画面の上から下の並び（間違いのある欄のうち、いちばん上にカーソルを移す）
export const FIELD_ORDER: FieldName[] = [
  'facility_name',
  'director_name',
  'email',
  'email_confirm',
  'password',
]

export type FieldErrors = Partial<Record<FieldName, string>>

// 施設名・施設長の名前の長さの上限（サーバーと同じ。backend/app/api/billing.py の SignupRequest）。
// 送る前に確かめないと、サーバーが 422 を返し、パスワードの欄に誤った理由が出てしまう
const NAME_MAX_LENGTH = 100

// サーバーと同じ形（backend/app/api/billing.py の SignupRequest.email）
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

export function isValidEmail(email: string): boolean {
  return email.length <= 254 && EMAIL_PATTERN.test(email)
}

/** 送る前の確認。間違いのある欄ごとに、辞書のキーを返す（なければ空）。 */
export function validateSignup(values: Record<FieldName, string>): FieldErrors {
  const errors: FieldErrors = {}
  const email = values.email.trim()
  const confirm = values.email_confirm.trim()

  for (const field of ['facility_name', 'director_name'] as const) {
    const name = values[field].trim()
    if (name === '') errors[field] = 'signup.error_required'
    // サーバーは文字数（Unicode のコードポイント）で数えるので、同じ数え方にする
    else if ([...name].length > NAME_MAX_LENGTH) errors[field] = 'signup.error_too_long'
  }

  if (email === '') errors.email = 'signup.error_required'
  else if (!isValidEmail(email)) errors.email = 'signup.email_invalid'

  if (confirm === '') errors.email_confirm = 'signup.error_required'
  else if (!errors.email && email !== confirm) errors.email_confirm = 'error.email_mismatch'

  if (values.password === '') errors.password = 'signup.error_required'
  else if (!isValidPassword(values.password)) errors.password = 'signup.password_invalid'

  return errors
}

/**
 * サーバーのエラーを、欄ごとの文言にする。欄が決まらないものは、フォーム全体のエラーにする。
 * - `email_mismatch`：確認用のメールアドレスの欄
 * - `validation_error`：送る前の確認で、ほかの欄は済ませているので、残るのはパスワード
 *   （よく使われるパスワードは、サーバーだけが知っている）
 */
export function placeServerError(errorKey: string): { field: FieldName | null; key: string } {
  if (errorKey === 'error.email_mismatch') return { field: 'email_confirm', key: errorKey }
  if (errorKey === 'error.validation_error')
    return { field: 'password', key: 'signup.password_common' }
  return { field: null, key: errorKey }
}
