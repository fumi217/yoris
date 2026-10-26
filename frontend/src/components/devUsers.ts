// 開発用の切り替えで選べる人（`GET /api/dev/users`。開発の環境だけ。spec 001 の contracts/api.md）
import type { StaffRole } from '../auth/me'
import type { Language } from '../i18n'
import { stripRuby } from '../i18n/rubyText'

export type DevUser = {
  user_id: number
  kind: 'staff' | 'family'
  role: StaffRole | null
  // 職員は返事に出す名前、家族は入居者の呼び名
  display_name: string
  language: Language
}

type Translate = (key: string, options?: Record<string, string>) => string

/**
 * 選ぶ欄に出す文字（`<option>` にはふりがなを出せないので、漢字だけにする）。
 * 職員は「名前／役割」。日本語でない人は言語も付ける（spec 007 を試すときに選びやすいように）。
 */
export function devUserLabel(user: DevUser, t: Translate): string {
  if (user.kind === 'family' || user.role === null) return user.display_name
  const role = stripRuby(t(`role.${user.role}`))
  // 言語が分からないとき（古い API）も、日本語と同じ形にする
  return !user.language || user.language === 'ja'
    ? t('dev.staff_label', { name: user.display_name, role })
    : t('dev.staff_label_with_language', {
        name: user.display_name,
        role,
        language: user.language,
      })
}
