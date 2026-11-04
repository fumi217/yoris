// 管理画面のトップ（#451）の、表示を決める小さな関数（画面から分けて、単体でテストできるようにする）。

import type { IconName } from '../../components/Icon'
import { themeIconName } from '../../components/themeIcon'
import type { Disclosure } from './DisclosureSettings'

const ITEM_ICON: Record<string, IconName> = {
  meal: 'meal',
  mood: 'mood',
  sleep: 'sleep',
  memo: 'memo',
}

/** 家族に見せていない項目・テーマ・機能の、辞書のキーとアイコン（開示設定の画面と同じ並び）。 */
export function hiddenLabels(disclosure: Disclosure): { key: string; icon: IconName }[] {
  return [
    ...disclosure.items
      .filter((item) => !item.visible)
      .map((item) => ({
        key: `disclosure.item.${item.code}`,
        icon: ITEM_ICON[item.code] ?? 'meal',
      })),
    ...disclosure.themes
      .filter((theme) => !theme.visible)
      .map((theme) => ({ key: theme.code, icon: themeIconName(theme.code) })),
    ...disclosure.features
      .filter((feature) => !feature.visible)
      .map((feature) => ({ key: `disclosure.feature.${feature.code}`, icon: 'album' as IconName })),
  ]
}
