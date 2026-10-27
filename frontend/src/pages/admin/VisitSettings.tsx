import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { ConfirmButton } from '../../components/ConfirmButton'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import { hhmm, monthDay, todayInJapan, weekdayOf } from '../family/visits/visitDates'
import {
  CANDIDATE_TIMES,
  clampDailyLimit,
  closedDaysRange,
  DAILY_LIMIT_MAX,
  DAILY_LIMIT_MIN,
  reasonProblem,
  reservationCountOf,
  toggleTime,
  type ClosedDay,
  type ClosedDayResult,
  type VisitSettingsData,
} from './visitSettingsRules'

const SETTINGS_KEY = ['admin', 'visit-settings']
const CLOSED_DAYS_KEY = ['admin', 'visit-closed-days']

/**
 * 面会の設定（UI-A02。spec 003 の T025。事務員・生活相談員・施設長。守りは API の 403）。
 * - 開始時刻の候補と、1 日に受け付ける組数を選んで「保存する」（FR-009）。
 *   候補から外した時刻の、すでに入っている予約はそのまま残る
 * - 休みの日を足す・やめる（FR-010）。予約が入っている日を休みにするときは、件数と、
 *   取り消しの理由の入力を出し、2 回押して、その日の予約を取り消してから休みにする（R-08。家族にお知らせとメール）
 */
export function VisitSettings() {
  const queryClient = useQueryClient()
  const settings = useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: () => api.get<VisitSettingsData>('/api/admin/visit-settings'),
  })
  // 保存の処理は、作り直す欄（下の key）の外に置く。欄の中に置くと、保存して値が変わったときに
  // 「保存しました」の状態も一緒に消えるため（PR #255 ようこ）
  const save = useMutation({
    mutationFn: (body: VisitSettingsData) =>
      api.put<VisitSettingsData>('/api/admin/visit-settings', body),
    onSuccess: (saved) => queryClient.setQueryData(SETTINGS_KEY, saved),
  })

  if (settings.isPending) return <Message k="layout.loading" />
  if (settings.isError) return <Message k={messageKeyOf(settings.error)} />
  return (
    <section className="space-y-8 p-4">
      <h1 className="text-xl font-bold">
        <Text k="visit_settings.title" />
      </h1>
      {/* 保存し直したら、読み直した値から始める */}
      <SettingsFormView
        key={JSON.stringify(settings.data)}
        initial={settings.data}
        saving={save.isPending}
        saved={save.isSuccess}
        errorKey={save.isError ? messageKeyOf(save.error) : null}
        onSave={(body) => save.mutate(body)}
      />
      <ClosedDays />
    </section>
  )
}

type SettingsFormProps = {
  initial: VisitSettingsData
  saving: boolean
  saved: boolean
  errorKey: string | null
  onSave: (body: VisitSettingsData) => void
}

/** 開始時刻の候補と組数（テストではこれを直接出す）。 */
export function SettingsFormView({ initial, saving, saved, errorKey, onSave }: SettingsFormProps) {
  const { t } = useTranslation()
  const [times, setTimes] = useState<string[]>(initial.start_times)
  const [limit, setLimit] = useState(initial.daily_limit)
  const noTime = times.length === 0

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (!noTime && !saving) onSave({ daily_limit: limit, start_times: times })
      }}
    >
      <fieldset>
        <legend className="font-bold">
          <Text k="visit_settings.times_title" />
        </legend>
        <p className="text-sm text-gray-600">
          <Text k="visit_settings.times_note" />
        </p>
        {/* 外せるのは「その時刻に始まる面会」だけ。その時刻を面会なしにする設定ではない */}
        <p className="mb-2 text-sm text-gray-600">
          <Text k="visit_settings.times_note_overlap" />
        </p>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {CANDIDATE_TIMES.map((time) => (
            <label
              key={time}
              className="flex items-center gap-2 rounded border-2 border-gray-300 p-2 has-[:checked]:border-sky-700"
            >
              <input
                type="checkbox"
                checked={times.includes(time)}
                onChange={() => setTimes((current) => toggleTime(current, time))}
              />
              {hhmm(time)}
            </label>
          ))}
        </div>
        {noTime && (
          <p role="alert" className="mt-2 text-red-700">
            <Text k="visit_settings.no_time" />
          </p>
        )}
      </fieldset>

      <fieldset>
        <legend className="font-bold">
          <Text k="visit_settings.daily_limit" />
        </legend>
        <div className="mt-2 flex items-center gap-3">
          <button
            type="button"
            aria-label={stripRuby(t('visit_settings.fewer'))}
            disabled={limit <= DAILY_LIMIT_MIN}
            onClick={() => setLimit((value) => clampDailyLimit(value - 1))}
            className="h-12 w-12 rounded border-2 border-gray-300 text-xl disabled:opacity-40"
          >
            −
          </button>
          <span className="min-w-16 text-center text-lg font-bold">
            <Ruby text={t('visit_settings.groups', { count: limit })} />
          </span>
          <button
            type="button"
            aria-label={stripRuby(t('visit_settings.more'))}
            disabled={limit >= DAILY_LIMIT_MAX}
            onClick={() => setLimit((value) => clampDailyLimit(value + 1))}
            className="h-12 w-12 rounded border-2 border-gray-300 text-xl disabled:opacity-40"
          >
            ＋
          </button>
        </div>
      </fieldset>

      <p className="text-sm text-gray-600">
        <Text k="visit_settings.kept_note" />
      </p>
      <p role="status" aria-live="polite" className="min-h-6 text-sm">
        {errorKey ? (
          <span className="text-red-700">
            <Text k={errorKey} />
          </span>
        ) : (
          saved && <Text k="visit_settings.saved" />
        )}
      </p>
      <button
        type="submit"
        disabled={noTime || saving}
        className="w-full rounded bg-sky-700 p-3 font-bold text-white disabled:opacity-50 sm:w-auto sm:px-8"
      >
        <Text k={saving ? 'visit_settings.saving' : 'visit_settings.save'} />
      </button>
    </form>
  )
}

// 予約が入っていた日（件数を出して、理由を入れて取り消すかを聞く）
type Pending = { date: string; count: number }

function ClosedDays() {
  const queryClient = useQueryClient()
  const today = todayInJapan()
  const range = closedDaysRange(today)
  const [pending, setPending] = useState<Pending | null>(null)
  const [notice, setNotice] = useState<{ key: string; count?: number } | null>(null)

  const days = useQuery({
    queryKey: [...CLOSED_DAYS_KEY, range.from, range.to],
    queryFn: () =>
      api.get<ClosedDay[]>(`/api/admin/visit-closed-days?from=${range.from}&to=${range.to}`),
  })
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: CLOSED_DAYS_KEY }),
      // 取り消した予約が、予約の一覧にも出る
      queryClient.invalidateQueries({ queryKey: ['admin', 'visits'] }),
    ])

  const close = useMutation({
    mutationFn: (body: { date: string; confirm_cancel?: boolean; reason?: string }) =>
      api.post<ClosedDayResult>('/api/admin/visit-closed-days', body),
    onMutate: () => setNotice(null),
    onSuccess: (result) => {
      setPending(null)
      setNotice(
        result.cancelled > 0
          ? { key: 'visit_settings.closed_notice_cancelled', count: result.cancelled }
          : { key: 'visit_settings.closed_notice' },
      )
    },
    onError: (error, body) => {
      const count = reservationCountOf(error)
      if (count !== null) setPending({ date: body.date, count })
    },
    onSettled: refresh,
  })
  const open = useMutation({
    mutationFn: (id: number) => api.delete(`/api/admin/visit-closed-days/${id}`),
    onMutate: () => setNotice(null),
    onSuccess: () => setNotice({ key: 'visit_settings.opened_notice' }),
    onSettled: refresh,
  })

  // 予約が入っていた（409）ことは、エラーではなく、確かめの欄で出す
  const failed =
    close.isError && reservationCountOf(close.error) === null
      ? close.error
      : open.isError
        ? open.error
        : null

  return (
    <ClosedDaysView
      today={today}
      days={days.data ?? null}
      loadErrorKey={days.isError ? messageKeyOf(days.error) : null}
      pending={pending}
      busy={close.isPending || open.isPending}
      notice={notice}
      errorKey={failed ? messageKeyOf(failed) : null}
      onClose={(date) => {
        setPending(null)
        close.mutate({ date })
      }}
      onConfirmClose={(date, reason) =>
        close.mutate({ date, confirm_cancel: true, reason: reason.trim() })
      }
      onDismiss={() => setPending(null)}
      onOpen={(id) => open.mutate(id)}
    />
  )
}

type ClosedDaysProps = {
  today: string
  // まだ読めていなければ null
  days: ClosedDay[] | null
  loadErrorKey: string | null
  pending: Pending | null
  busy: boolean
  notice: { key: string; count?: number } | null
  errorKey: string | null
  onClose: (date: string) => void
  onConfirmClose: (date: string, reason: string) => void
  onDismiss: () => void
  onOpen: (id: number) => void
}

/** 休みの日の欄（テストではこれを直接出す）。 */
export function ClosedDaysView({
  today,
  days,
  loadErrorKey,
  pending,
  busy,
  notice,
  errorKey,
  onClose,
  onConfirmClose,
  onDismiss,
  onOpen,
}: ClosedDaysProps) {
  const { t } = useTranslation()
  const [date, setDate] = useState('')
  const formatDate = (value: string) =>
    t('visit.date', {
      ...monthDay(value),
      weekday: stripRuby(t(`visit.weekday.${weekdayOf(value)}`)),
    })

  return (
    <section className="space-y-4 border-t pt-6">
      <h2 className="font-bold">
        <Text k="visit_settings.closed_title" />
      </h2>

      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (date && !busy) onClose(date)
        }}
      >
        <label className="text-sm">
          <Text k="visit_settings.closed_date" />
          <input
            type="date"
            value={date}
            min={today}
            onChange={(event) => setDate(event.target.value)}
            className="mt-1 block rounded border-2 border-gray-300 p-2"
          />
        </label>
        <button
          type="submit"
          disabled={!date || busy}
          className="rounded bg-sky-700 px-4 py-2 font-bold text-white disabled:opacity-50"
        >
          <Text k="visit_settings.close" />
        </button>
      </form>

      {pending && (
        <ReservationsWarning
          key={pending.date}
          pending={pending}
          label={formatDate(pending.date)}
          busy={busy}
          onConfirm={(reason) => onConfirmClose(pending.date, reason)}
          onDismiss={onDismiss}
        />
      )}

      <p role="status" aria-live="polite" className="min-h-6 text-sm">
        {errorKey ? (
          <span className="text-red-700">
            <Text k={errorKey} />
          </span>
        ) : (
          notice && <Ruby text={t(notice.key, { count: notice.count })} />
        )}
      </p>

      {loadErrorKey ? (
        <p className="text-red-700">
          <Text k={loadErrorKey} />
        </p>
      ) : days === null ? null : days.length === 0 ? (
        <p className="text-sm text-gray-600">
          <Text k="visit_settings.closed_empty" />
        </p>
      ) : (
        <ul className="divide-y rounded border">
          {days.map((day) => (
            <li key={day.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
              <span className="font-bold">
                <Ruby text={formatDate(day.closed_date)} />
              </span>
              <ConfirmButton
                labelKey="visit_settings.open"
                confirmKey="visit_settings.open_confirm"
                disabled={busy}
                onConfirm={() => onOpen(day.id)}
                className="rounded border-2 border-gray-300 px-3 py-1 text-sm"
              />
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-gray-600">
        <Text k="visit_settings.open_note" />
      </p>
    </section>
  )
}

type WarningProps = {
  pending: Pending
  // 日付の文言（ふりがなの書き方を含む）
  label: string
  busy: boolean
  onConfirm: (reason: string) => void
  onDismiss: () => void
}

/** 予約が入っている日を休みにするときの、件数と理由の入力（R-08）。 */
function ReservationsWarning({ pending, label, busy, onConfirm, onDismiss }: WarningProps) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const problem = reasonProblem(reason)

  return (
    <div role="alert" className="space-y-3 rounded border-2 border-orange-600 bg-orange-50 p-3">
      <p className="font-bold">
        <Ruby text={label} />
      </p>
      <p>
        <Ruby text={t('visit_settings.has_reservations', { count: pending.count })} />
      </p>
      <label className="block text-sm">
        <Text k="visit_settings.reason" />
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={2}
          aria-invalid={problem === 'too_long'}
          className="mt-1 block w-full rounded border-2 border-gray-300 p-2 aria-[invalid=true]:border-red-700"
        />
      </label>
      {problem === 'too_long' && (
        <p className="text-red-700">
          <Text k="visit_settings.reason_too_long" />
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <ConfirmButton
          labelKey="visit_settings.confirm_close"
          confirmKey="visit_settings.confirm_close_confirm"
          busyKey="visit_settings.closing"
          busy={busy}
          disabled={problem !== null || busy}
          onConfirm={() => onConfirm(reason)}
          className="rounded bg-orange-700 px-4 py-2 font-bold text-white disabled:opacity-50"
        />
        <button type="button" onClick={onDismiss} className="text-sm text-gray-700 underline">
          <Text k="visit_settings.dismiss" />
        </button>
      </div>
    </div>
  )
}
