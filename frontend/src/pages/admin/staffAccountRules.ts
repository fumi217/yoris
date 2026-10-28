// 職員のアカウントを作る画面（001-T088）の、API の形と、選べる値・確かめの決まり。
// 画面（StaffAccounts.tsx）と分けて、単体でテストできるようにしている。
// 最終の判定はバックエンド（backend/app/api/admin/staff.py）が行う。

// 役割（画面と API で何ができるか）。backend の STAFF_ROLES と同じ
export const ROLES = ['care_worker', 'leader', 'counselor', 'clerk', 'director'] as const
export type StaffRoleCode = (typeof ROLES)[number]

// 職種（家族の画面の「名前（職種）」に出す表示）。backend の STAFF_OCCUPATIONS と同じ。
// 看護師・機能訓練指導員・ケアマネジャーの役割は、介護職員（care_worker）
export const OCCUPATIONS = [
  'care_worker',
  'leader',
  'counselor',
  'clerk',
  'director',
  'nurse',
  'functional_trainer',
  'care_manager',
] as const
export type OccupationCode = (typeof OCCUPATIONS)[number]

// 表示名の文字数の上限（backend の DISPLAY_NAME_MAX）
export const DISPLAY_NAME_MAX = 20

export type StaffCreateBody = {
  display_name: string
  role: StaffRoleCode
  occupation: OccupationCode | null
}

export type CreatedStaff = {
  id: number
  login_id: string
  display_name: string
  role: StaffRoleCode
  occupation: OccupationCode | null
  // 作った直後の返事でだけ返ってくる。あとからは見られない
  initial_password: string
}

export type NameProblem = 'empty' | 'too_long'

/** 表示名の確かめ（前後の空白を除いて 1〜20 文字）。問題がなければ null。 */
export function nameProblem(name: string): NameProblem | null {
  // 絵文字などを 1 文字と数える（backend は文字の数で数える）
  const length = [...name.trim()].length
  if (length === 0) return 'empty'
  if (length > DISPLAY_NAME_MAX) return 'too_long'
  return null
}

/** 送る中身にする。表示名の前後の空白は除き、職種は選ばなかったら null。 */
export function toBody(name: string, role: StaffRoleCode, occupation: string): StaffCreateBody {
  return {
    display_name: name.trim(),
    role,
    occupation: occupation === '' ? null : (occupation as OccupationCode),
  }
}
