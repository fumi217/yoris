import { useTranslation } from 'react-i18next'
import { Icon } from '../../components/Icon'
import { Text } from '../../components/Text'
import { stripRuby } from '../../i18n/rubyText'
import { monthDayOf, pickDate, shiftDate, weekdayOf } from './contactBookView'

type Props = {
  // 見ている日（"2026-10-30"）と、今日
  date: string
  today: string
  onMove: (date: string) => void
}

const arrow =
  'flex min-h-11 min-w-11 items-center justify-center rounded-full text-primary hover:bg-primary-soft disabled:text-ink-sub disabled:opacity-40 disabled:hover:bg-transparent'

const textButton =
  'min-h-11 rounded-xl bg-primary-soft px-3 text-sm font-bold text-primary-dark hover:bg-primary hover:text-white'

/**
 * 見る日の切り替え（連絡帳。#382）。見出しの行に近い、軽い見た目にする（枠線・影・背景の箱はなし）。
 * ふだんは、前の日・今の日付・次の日の 3 つだけ。矢印のボタンは、名前を付ける（「前の日」「次の日」。
 * アイコンだけなので aria-label。4.1.2）。今日より先は選べない（記録がないため）ので、押せない間は
 * 「明日の記録は、まだありません」と近くに書く（デザインの決めごと 7 章。aria-describedby でも結ぶ）。
 * もっと前の日は、「もっと前の日を見る」を開いたときだけ、日付の入力（ネイティブの日付の選び）を出す。
 * 過去の日を見ているときだけ「今日の連絡帳に戻る」も出す。押せる大きさは 44px 以上（2.5.8）。
 */
export function DateNavigator({ date, today, onMove }: Props) {
  const { t, i18n } = useTranslation()
  const isToday = date === today
  const label = t('contact_book.date_label', {
    ...monthDayOf(date),
    weekday: weekdayOf(date, i18n.language),
  })

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <button
          type="button"
          aria-label={stripRuby(t('contact_book.prev_day'))}
          className={arrow}
          onClick={() => onMove(shiftDate(date, -1))}
        >
          <Icon name="prev" />
        </button>
        <span aria-live="polite" className="min-w-32 text-center font-bold">
          {stripRuby(label)}
        </span>
        <button
          type="button"
          aria-label={stripRuby(t('contact_book.next_day'))}
          aria-describedby={isToday ? 'next-day-hint' : undefined}
          className={arrow}
          disabled={isToday}
          onClick={() => onMove(shiftDate(date, 1))}
        >
          <Icon name="next" />
        </button>
        {!isToday && (
          <button type="button" className={textButton} onClick={() => onMove(today)}>
            <Text k="contact_book.go_today" />
          </button>
        )}
      </div>
      {isToday && (
        <p id="next-day-hint" className="text-sm text-ink-sub">
          <Text k="contact_book.next_unavailable" />
        </p>
      )}

      <details>
        <summary className="inline-flex min-h-11 cursor-pointer items-center gap-2 text-sm text-primary underline">
          <Icon name="date" />
          <Text k="contact_book.more_dates" />
        </summary>
        <label className="mt-1 flex flex-wrap items-center gap-2 text-sm">
          <Text k="contact_book.pick_date" />
          <input
            type="date"
            value={date}
            max={today}
            onChange={(event) => {
              const picked = pickDate(event.target.value, today)
              if (picked !== date) onMove(picked)
            }}
            className="min-h-11 rounded border border-field-line bg-white px-2"
          />
        </label>
      </details>
    </div>
  )
}
