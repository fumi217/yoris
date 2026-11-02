import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Icon } from '../../../components/Icon'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError, api, messageKeyOf } from '../../../api/client'
import { Message } from '../../../components/Message'
import { Text } from '../../../components/Text'
import { Ruby } from '../../../i18n/Ruby'
import { stripRuby } from '../../../i18n/rubyText'
import { MyVisits } from './MyVisits'
import {
  bookingRange,
  dayStatus,
  endOf,
  hhmm,
  monthDay,
  calendarCells,
  monthOf,
  monthsBetween,
  todayInJapan,
  weekdayOf,
  type Availability,
  type Day,
  type Reservation,
  MY_VISITS_KEY,
} from './visitDates'

type Booking = { visit_date: string; start_time: string; party_size: number }

/**
 * 家族の面会の予約の画面（UI-F01。spec 003 の T012・T014。`/family/visits`）。
 * 日付 → 開始時刻（選べないものは押せない）→ 人数 → 「予約する」。開いてから確定まで 5 タップ以内（SC-001）。
 * 入居者は送らない（サーバーがログイン中の家族から決める。FR-020）。
 * 409（ほかの家族が先に予約した など）のときは、文言を出して空きを読み直す。
 */
export function VisitBooking() {
  const queryClient = useQueryClient()
  const { from, to } = bookingRange(todayInJapan())
  const queryKey = ['family', 'visits', 'availability', from, to]

  const availability = useQuery({
    queryKey,
    queryFn: () => api.get<Availability>(`/api/family/visits/availability?from=${from}&to=${to}`),
  })
  const book = useMutation({
    mutationFn: (booking: Booking) => api.post<Reservation>('/api/family/visits', booking),
    // 空きと、いちばん上の「これからの予約」を読み直す
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: MY_VISITS_KEY }),
      ]),
  })

  if (availability.isPending) return <Message k="layout.loading" />
  if (availability.isError) return <Message k={messageKeyOf(availability.error)} />
  return (
    <BookingView
      // 自分の予約（003-T018）。題のすぐ下に出す
      mine={<MyVisits />}
      days={availability.data.days}
      booking={book.isPending}
      confirmed={book.isSuccess ? book.data : null}
      errorKey={book.isError ? messageKeyOf(book.error) : null}
      onBook={(booking, onConflict) =>
        book.mutate(booking, {
          onError: (error) => {
            if (error instanceof ApiError && error.status === 409) onConflict()
          },
        })
      }
      onReset={() => book.reset()}
    />
  )
}

type ViewProps = {
  days: Day[]
  booking: boolean
  confirmed: Reservation | null
  errorKey: string | null
  // onConflict は 409 のときに呼ばれる（選んでいた時刻を外し、読み直した空きで選び直してもらう）
  onBook: (booking: Booking, onConflict: () => void) => void
  onReset: () => void
  // 初めから選んでおく日付（テスト用。画面では選ばない状態から始める）
  initialDate?: string | null
  // 題のすぐ下に出す「これからの予約」（MyVisits）
  mine?: ReactNode
}

/** 画面の中身（テストではこれを直接出す）。 */
export function BookingView({
  days,
  booking,
  confirmed,
  errorKey,
  onBook,
  onReset,
  initialDate = null,
  mine = null,
}: ViewProps) {
  const { t } = useTranslation()
  const [date, setDate] = useState<string | null>(initialDate)
  const [time, setTime] = useState<string | null>(null)
  const [partySize, setPartySize] = useState(1)
  // 出している月（0 が明日の月。初めから日付を選んでいるときは、その月）
  const [monthIndex, setMonthIndex] = useState(() =>
    initialDate
      ? Math.max(0, monthsBetween(days[0]?.date ?? initialDate, initialDate).length - 1)
      : 0,
  )

  const dateLabel = (value: string) =>
    t('visit.date', {
      ...monthDay(value),
      weekday: stripRuby(t(`visit.weekday.${weekdayOf(value)}`)),
    })

  const summaryOf = (value: { date: string; start: string; people: number }) =>
    t('visit.confirmed_detail', {
      date: dateLabel(value.date),
      time: t('visit.time_range', { start: value.start, end: endOf(value.start) }),
      people: t('visit.people', { count: value.people }),
    })

  if (confirmed) {
    return (
      <section className="space-y-5 p-4" role="status">
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-card-line bg-card px-4 py-6 text-center">
          <span
            aria-hidden="true"
            className="flex size-14 items-center justify-center rounded-full bg-[#dcfce7] text-[#166534]"
          >
            <Icon name="check" className="text-3xl" />
          </span>
          <h1 className="text-xl font-bold">
            <Text k="visit.confirmed" />
          </h1>
          <p className="text-lg font-bold tabular-nums">
            <Ruby
              text={summaryOf({
                date: confirmed.visit_date,
                start: hhmm(confirmed.start_time),
                people: confirmed.party_size,
              })}
            />
          </p>
          <p className="text-sm text-ink-sub">
            <Text k="visit.confirmed_note" />
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setDate(null)
            setTime(null)
            onReset()
          }}
          className="flex min-h-12 w-full items-center justify-center rounded-xl border border-field-line bg-white font-bold shadow-sm"
        >
          <Text k="visit.book_another" />
        </button>
        {mine}
      </section>
    )
  }

  const selectedDay = days.find((day) => day.date === date)
  const byDate = new Map(days.map((day) => [day.date, day]))
  const months = days.length ? monthsBetween(days[0].date, days[days.length - 1].date) : []
  const month = months[Math.min(monthIndex, months.length - 1)] ?? monthOf(todayInJapan())

  return (
    <section className="space-y-5 p-4">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">
          <Text k="visit.title" />
        </h1>
        <p className="flex items-start gap-2 rounded-xl bg-primary-soft p-3 text-sm">
          <Icon name="info" className="mt-0.5 shrink-0 text-primary" />
          <Text k="visit.hours_note" />
        </p>
      </div>

      {mine}

      {errorKey && (
        <p role="alert" className="rounded border border-red-700 bg-white p-3 text-red-700">
          <Text k={errorKey} />
        </p>
      )}

      <StepCard number={1} titleKey="visit.choose_date">
        <div className="mb-2 flex items-center justify-between">
          <button
            type="button"
            aria-label={stripRuby(t('visit.previous_month'))}
            disabled={monthIndex === 0}
            onClick={() => setMonthIndex((index) => index - 1)}
            className="flex size-11 items-center justify-center rounded-full text-primary hover:bg-primary-soft disabled:text-ink-sub disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <Icon name="prev" />
          </button>
          <span className="font-bold">
            <Ruby text={t('visit.month', yearMonth(month))} />
          </span>
          <button
            type="button"
            aria-label={stripRuby(t('visit.next_month'))}
            disabled={monthIndex >= months.length - 1}
            onClick={() => setMonthIndex((index) => index + 1)}
            className="flex size-11 items-center justify-center rounded-full text-primary hover:bg-primary-soft disabled:text-ink-sub disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <Icon name="next" />
          </button>
        </div>
        <div className="grid grid-cols-7 gap-1 text-center">
          {[0, 1, 2, 3, 4, 5, 6].map((weekday) => (
            <span key={weekday} className="pb-0.5 text-xs text-ink-sub">
              <Text k={`visit.weekday.${weekday}`} />
            </span>
          ))}
          {calendarCells(month).map((cell, index) => {
            if (cell === null) return <span key={`empty-${index}`} />
            const day = byDate.get(cell)
            // 予約できる期間（明日〜28 日先）の外の日は、数字だけを出して押せない
            if (!day) {
              return (
                <span
                  key={cell}
                  className="flex min-h-14 items-center justify-center text-gray-300"
                >
                  {monthDay(cell).day}
                </span>
              )
            }
            const status = dayStatus(day)
            const selected = day.date === date
            return (
              <button
                key={day.date}
                type="button"
                aria-pressed={selected}
                aria-label={stripRuby(dateLabel(day.date))}
                disabled={status !== 'open'}
                onClick={() => {
                  setDate(day.date)
                  setTime(null)
                }}
                className={`flex min-h-14 flex-col items-center justify-center rounded-xl border leading-tight tabular-nums ${
                  selected
                    ? 'border-primary bg-primary font-bold text-white shadow-md'
                    : status === 'mine'
                      ? 'border-primary-soft bg-primary-soft font-bold text-primary-dark'
                      : status === 'full'
                        ? 'border-page bg-page text-ink-sub'
                        : 'border-card-line bg-white hover:bg-primary-soft'
                }`}
              >
                {monthDay(day.date).day}
                {status !== 'open' && (
                  // 12px。短い 2 行（「予約／済み」「空き／なし」）にして、マスの中で折れる位置をそろえる
                  <span className="block text-xs leading-tight whitespace-pre-line">
                    <Text k={status === 'mine' ? 'visit.booked_cell' : 'visit.full_cell'} />
                  </span>
                )}
              </button>
            )
          })}
        </div>
        {/* 色だけで伝えない：どの色が何かを、文字でも添える（1.4.1） */}
        <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-sub">
          <Legend className="border-card-line bg-white" labelKey="visit.legend_open" />
          <Legend className="border-primary-soft bg-primary-soft" labelKey="visit.booked_day" />
          <Legend className="border-page bg-page" labelKey="visit.no_slot" />
        </p>
      </StepCard>

      {selectedDay && (
        <StepCard
          number={2}
          titleKey="visit.choose_time"
          sub={<Ruby text={dateLabel(selectedDay.date)} />}
        >
          {selectedDay.start_times.some((slot) => slot.selectable) ? (
            <div className="grid grid-cols-2 gap-2">
              {selectedDay.start_times.map((slot) => {
                const start = hhmm(slot.start_time)
                const selected = slot.start_time === time
                return (
                  <button
                    key={slot.start_time}
                    type="button"
                    aria-pressed={selected}
                    disabled={!slot.selectable}
                    onClick={() => setTime(slot.start_time)}
                    className={`min-h-12 rounded-xl border tabular-nums ${
                      selected
                        ? 'border-primary bg-primary font-bold text-white shadow-md'
                        : slot.selectable
                          ? 'border-card-line bg-white hover:bg-primary-soft'
                          : 'border-page bg-page text-ink-sub line-through'
                    }`}
                  >
                    {t('visit.time_range', { start, end: endOf(start) })}
                  </button>
                )
              })}
            </div>
          ) : (
            <Message k="visit.no_time" />
          )}
        </StepCard>
      )}

      {selectedDay && time && (
        <StepCard number={3} titleKey="visit.party_size">
          <div className="flex items-center justify-center gap-6">
            <button
              type="button"
              aria-label={stripRuby(t('visit.fewer'))}
              disabled={partySize <= 1}
              onClick={() => setPartySize((size) => Math.max(1, size - 1))}
              className="size-12 rounded-full border border-field-line bg-white text-2xl text-primary-dark shadow-sm disabled:opacity-40"
            >
              −
            </button>
            <span className="min-w-24 text-center text-2xl font-bold" aria-live="polite">
              <Ruby text={t('visit.people', { count: partySize })} />
            </span>
            <button
              type="button"
              aria-label={stripRuby(t('visit.more'))}
              onClick={() => setPartySize((size) => size + 1)}
              className="size-12 rounded-full border border-field-line bg-white text-2xl text-primary-dark shadow-sm"
            >
              ＋
            </button>
          </div>
        </StepCard>
      )}

      {selectedDay && time && (
        <div className="space-y-2">
          <button
            type="button"
            disabled={booking}
            onClick={() =>
              onBook(
                { visit_date: selectedDay.date, start_time: time, party_size: partySize },
                () => setTime(null),
              )
            }
            className="flex min-h-14 w-full items-center justify-center gap-2 rounded-2xl bg-primary text-lg font-bold text-white shadow-md disabled:opacity-60"
          >
            <Icon name="check" />
            <Text k={booking ? 'visit.booking' : 'visit.book'} />
          </button>
          {/* 押す前に、選んだ内容をもう一度見せる */}
          <p className="text-center text-sm text-ink-sub">
            <Ruby
              text={summaryOf({ date: selectedDay.date, start: hhmm(time), people: partySize })}
            />
          </p>
        </div>
      )}
    </section>
  )
}

/** 手順の白い面：丸い番号・見出し・（右に補足）。見出しで、面の名前を付ける（読み上げ用）。 */
function StepCard({
  number,
  titleKey,
  sub,
  children,
}: {
  number: number
  titleKey: string
  // 見出しの下に出す補足（手順 2 の、選んだ日付。横に並べると、見出しが折れるため）
  sub?: ReactNode
  children: ReactNode
}) {
  const headingId = `visit-step-${number}`
  return (
    <section
      aria-labelledby={headingId}
      className="rounded-2xl border border-card-line bg-card p-4"
    >
      <div className="mb-3 flex items-center gap-2.5">
        <span
          aria-hidden="true"
          className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-white"
        >
          {number}
        </span>
        <h2 id={headingId} className="font-bold">
          <Text k={titleKey} />
        </h2>
      </div>
      {sub && <p className="-mt-1.5 mb-3 ml-[2.125rem] text-sm text-ink-sub">{sub}</p>}
      {children}
    </section>
  )
}

/** カレンダーの見分けの小さな見本。 */
function Legend({ className, labelKey }: { className: string; labelKey: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden="true" className={`inline-block size-3 rounded border ${className}`} />
      <Text k={labelKey} />
    </span>
  )
}

/** "2026-10" → { year: 2026, month: 10 } */
function yearMonth(month: string): { year: number; month: number } {
  const [year, value] = month.split('-').map(Number)
  return { year, month: value }
}
