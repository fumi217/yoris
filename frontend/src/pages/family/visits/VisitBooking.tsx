import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError, api, messageKeyOf } from '../../../api/client'
import { Message } from '../../../components/Message'
import { Text } from '../../../components/Text'
import { Ruby } from '../../../i18n/Ruby'
import { stripRuby } from '../../../i18n/rubyText'
import {
  bookingRange,
  dayStatus,
  endOf,
  hhmm,
  monthDay,
  todayInJapan,
  weekdayOf,
  type Availability,
  type Day,
  type Reservation,
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
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  })

  if (availability.isPending) return <Message k="layout.loading" />
  if (availability.isError) return <Message k={messageKeyOf(availability.error)} />
  return (
    <BookingView
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
}: ViewProps) {
  const { t } = useTranslation()
  const [date, setDate] = useState<string | null>(initialDate)
  const [time, setTime] = useState<string | null>(null)
  const [partySize, setPartySize] = useState(1)

  const dateLabel = (value: string) =>
    t('visit.date', {
      ...monthDay(value),
      weekday: stripRuby(t(`visit.weekday.${weekdayOf(value)}`)),
    })

  if (confirmed) {
    const start = hhmm(confirmed.start_time)
    return (
      <section className="space-y-4 p-4" role="status">
        <h1 className="text-xl font-bold">
          <Text k="visit.confirmed" />
        </h1>
        <p className="text-lg">
          <Ruby
            text={t('visit.confirmed_detail', {
              date: dateLabel(confirmed.visit_date),
              time: t('visit.time_range', { start, end: endOf(start) }),
              people: t('visit.people', { count: confirmed.party_size }),
            })}
          />
        </p>
        <button
          type="button"
          onClick={() => {
            setDate(null)
            setTime(null)
            onReset()
          }}
          className="text-sky-700 underline"
        >
          <Text k="visit.book_another" />
        </button>
      </section>
    )
  }

  const selectedDay = days.find((day) => day.date === date)

  return (
    <section className="space-y-6 p-4">
      <div>
        <h1 className="text-xl font-bold">
          <Text k="visit.title" />
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          <Text k="visit.hours_note" />
        </p>
      </div>

      {errorKey && (
        <p role="alert" className="rounded border border-red-700 p-3 text-red-700">
          <Text k={errorKey} />
        </p>
      )}

      <fieldset>
        <legend className="mb-2 font-bold">
          <Text k="visit.choose_date" />
        </legend>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {days.map((day) => {
            const status = dayStatus(day)
            const selected = day.date === date
            return (
              <button
                key={day.date}
                type="button"
                aria-pressed={selected}
                disabled={status !== 'open'}
                onClick={() => {
                  setDate(day.date)
                  setTime(null)
                }}
                className={`rounded border-2 p-2 text-left disabled:bg-gray-100 disabled:text-gray-500 ${
                  selected ? 'border-sky-700 bg-sky-700 text-white' : 'border-gray-300'
                }`}
              >
                <Ruby text={dateLabel(day.date)} />
                {status !== 'open' && (
                  <span className="block text-xs">
                    <Text k={status === 'mine' ? 'visit.booked_day' : 'visit.no_slot'} />
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </fieldset>

      {selectedDay && (
        <fieldset>
          <legend className="mb-2 font-bold">
            <Text k="visit.choose_time" />
          </legend>
          {selectedDay.start_times.some((slot) => slot.selectable) ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
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
                    className={`min-h-12 rounded border-2 p-2 disabled:bg-gray-100 disabled:text-gray-400 disabled:line-through ${
                      selected ? 'border-sky-700 bg-sky-700 text-white' : 'border-gray-300'
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
        </fieldset>
      )}

      {selectedDay && time && (
        <fieldset>
          <legend className="mb-2 font-bold">
            <Text k="visit.party_size" />
          </legend>
          <div className="flex items-center gap-4">
            <button
              type="button"
              aria-label={stripRuby(t('visit.fewer'))}
              disabled={partySize <= 1}
              onClick={() => setPartySize((size) => Math.max(1, size - 1))}
              className="h-12 w-12 rounded border-2 border-gray-300 text-xl disabled:opacity-40"
            >
              −
            </button>
            <span className="min-w-12 text-center text-lg" aria-live="polite">
              <Ruby text={t('visit.people', { count: partySize })} />
            </span>
            <button
              type="button"
              aria-label={stripRuby(t('visit.more'))}
              onClick={() => setPartySize((size) => size + 1)}
              className="h-12 w-12 rounded border-2 border-gray-300 text-xl"
            >
              ＋
            </button>
          </div>
        </fieldset>
      )}

      {selectedDay && time && (
        <button
          type="button"
          disabled={booking}
          onClick={() =>
            onBook({ visit_date: selectedDay.date, start_time: time, party_size: partySize }, () =>
              setTime(null),
            )
          }
          className="w-full rounded bg-sky-700 p-4 text-lg font-bold text-white disabled:opacity-60"
        >
          <Text k={booking ? 'visit.booking' : 'visit.book'} />
        </button>
      )}
    </section>
  )
}
