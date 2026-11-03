import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { stripRuby } from '../i18n/rubyText'
import { Icon, type IconName } from './Icon'
import { Text } from './Text'

/** 行き先のタブの 1 つ。 */
export type TabItem = {
  to: string
  // 辞書のキー（日本語は、ふりがな付きの書き方）。狭い幅でも並ぶよう、短い名前にする
  labelKey: string
  icon: IconName
  // 件数（1 件以上のときだけ出す。通知・音は出さない）
  count?: number
  // 今の画面がこのタブに当たるか（詳細の画面でも、もとのタブを選ばれた状態にするため）
  isActive: (pathname: string) => boolean
}

// 1 段に並べる数（4 つまで。5 つ以上は、4 つずつの段にする）
const COLUMNS = ['grid-cols-1', 'grid-cols-2', 'grid-cols-3', 'grid-cols-4']

/**
 * 職員の画面・管理画面の、行き先のタブ（デザインの決めごと 8 章。#437）。
 * アイコンの下に文字を置くタイルを、1 段に 4 つまで並べる（家族の画面の下のメニューと同じ形）。
 * 横にはみ出さず、隠れるタブがない（タブレット 617px・スマホ 320px でも、すべて見える。1.4.10）。
 * 選ばれたタブは、色に加えて、太字・薄い青の背景・下の線と、`aria-current="page"` で示す（1.4.1）。
 * 件数は、赤い丸（飾り）に加えて、読み上げ用の文字でも伝える。押す所は 44px 以上（2.5.8）。
 */
export function AreaTabs({ items, labelKey }: { items: TabItem[]; labelKey: string }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  return (
    <nav aria-label={stripRuby(t(labelKey))} className="border-t border-card-line">
      <ul className={`grid gap-1 p-1.5 ${COLUMNS[Math.min(items.length, 4) - 1] ?? 'grid-cols-4'}`}>
        {items.map((item) => {
          const active = item.isActive(pathname)
          return (
            <li key={item.to} className="min-w-0">
              <Link
                to={item.to}
                aria-current={active ? 'page' : undefined}
                className={`flex h-full min-h-14 flex-col items-center justify-center gap-0.5 rounded-xl px-1 py-1.5 text-center text-xs leading-tight break-keep [overflow-wrap:anywhere] sm:text-sm ${
                  active
                    ? 'bg-primary-soft font-bold text-primary-dark shadow-[inset_0_-3px_0_var(--color-primary)]'
                    : 'font-semibold text-ink-sub hover:bg-page hover:text-ink'
                }`}
              >
                <span className="relative">
                  <Icon name={item.icon} className="text-lg" />
                  {item.count !== undefined && item.count > 0 && (
                    <span
                      aria-hidden="true"
                      className="absolute -top-1.5 left-full ml-0.5 inline-flex h-[20px] min-w-[20px] items-center justify-center rounded-full bg-danger px-1 text-xs font-bold text-white"
                    >
                      {item.count}
                    </span>
                  )}
                </span>
                <span className="max-w-full">
                  <Text k={item.labelKey} />
                </span>
                {item.count !== undefined && item.count > 0 && (
                  <span className="sr-only">
                    {stripRuby(t('layout.tab_count', { count: item.count }))}
                  </span>
                )}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
