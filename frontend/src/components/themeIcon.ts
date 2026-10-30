import type { IconName } from './Icon'

// テーマのコード → アイコン（絵文字はやめた。デザインの決めごと 14.2。#385・#388）。
// 家族の画面・職員の画面・管理画面で、同じテーマには同じアイコンを使う
const THEME_ICONS: Record<string, IconName> = {
  'theme.daily_life': 'theme-daily-life',
  'theme.enjoying': 'theme-enjoying',
  'theme.residents': 'theme-residents',
  'theme.meals': 'theme-meals',
  'theme.staff': 'theme-staff',
  'theme.recreation': 'theme-recreation',
  'theme.family_talk': 'theme-family-talk',
  'theme.supplies': 'theme-supplies',
}

export function themeIconName(code: string): IconName {
  return THEME_ICONS[code] ?? 'requests'
}
