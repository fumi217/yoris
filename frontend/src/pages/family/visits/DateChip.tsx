import { useTranslation } from 'react-i18next'
import { stripRuby } from '../../../i18n/rubyText'
import { monthDay, monthShort, weekdayOf } from './visitDates'

/**
 * 予約の行の左の、日付の札（月・日・曜日。#404）。飾り（読み上げない）。同じ内容は、行の文字にもある。
 * 取り消された予約は、グレーにする。
 */
export function DateChip({ date, active = true }: { date: string; active?: boolean }) {
  const { t, i18n } = useTranslation()
  return (
    <span
      aria-hidden="true"
      className={`flex w-14 shrink-0 flex-col items-center rounded-xl py-1 leading-tight ${
        active ? 'bg-primary-soft text-primary-dark' : 'bg-page text-ink-sub'
      }`}
    >
      <span className="text-xs font-bold">{monthShort(date, i18n.language)}</span>
      <span className="text-xl font-bold tabular-nums">{monthDay(date).day}</span>
      <span className="text-xs font-bold">{stripRuby(t(`visit.weekday.${weekdayOf(date)}`))}</span>
    </span>
  )
}
