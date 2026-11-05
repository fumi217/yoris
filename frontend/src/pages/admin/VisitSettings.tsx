import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { ConfirmButton } from '../../components/ConfirmButton'
import { Icon } from '../../components/Icon'
import { Message } from '../../components/Message'
import { ReasonField } from '../../components/ReasonField'
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
    // 下の余白は、保存の帯（fixed）に隠れないように、いつも付ける（帯が出入りしても、中身がずれない）
    <section className="space-y-4 p-4 pb-24">
      <div>
        <h1 className="text-2xl font-bold">
          <Text k="visit_settings.title" />
        </h1>
        <p className="mt-1 text-sm text-ink-sub">
          <Text k="visit_settings.lead" />
        </p>
      </div>
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

/**
 * 開始時刻の候補と組数（テストではこれを直接出す）。
 * 見た目（#453）：白い面に、時刻は押して選ぶ札、組数は −／＋。保存は、変えたときだけ下に出る帯。
 */
export function SettingsFormView({ initial, saving, saved, errorKey, onSave }: SettingsFormProps) {
  const { t } = useTranslation()
  const [times, setTimes] = useState<string[]>(initial.start_times)
  const [limit, setLimit] = useState(initial.daily_limit)
  const noTime = times.length === 0
  const changed = limit !== initial.daily_limit || times.join(',') !== initial.start_times.join(',')

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (!noTime && !saving) onSave({ daily_limit: limit, start_times: times })
      }}
    >
      <p role="status" aria-live="polite" className="text-sm empty:hidden">
        {saved && !changed && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 font-bold text-green-800">
            <Icon name="check" />
            <Text k="visit_settings.saved" />
          </span>
        )}
      </p>

      <div className="divide-y divide-card-line overflow-hidden rounded-xl border border-card-line bg-card">
        <fieldset className="px-4 py-3.5">
          <legend className="float-left w-full font-bold">
            <Icon name="upload-waiting" className="mr-2 text-primary" />
            <Text k="visit_settings.times_title" />
          </legend>
          <p className="clear-left pt-1 text-sm text-ink-sub">
            <Text k="visit_settings.times_note" />
          </p>
          {/* 外せるのは「その時刻に始まる面会」だけ。その時刻を面会なしにする設定ではない */}
          <p className="mb-3 text-sm text-ink-sub">
            <Text k="visit_settings.times_note_overlap" />
          </p>
          <div className="grid grid-cols-3 gap-2 min-[480px]:grid-cols-4 sm:grid-cols-6">
            {CANDIDATE_TIMES.map((time) => {
              const on = times.includes(time)
              return (
                // 選んだ時刻は、薄い青の背景・青の枠・✓ で示す（色だけに頼らない）
                <label
                  key={time}
                  className={`flex min-h-11 cursor-pointer items-center justify-center gap-1.5 rounded-lg font-bold tabular-nums has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary ${
                    on
                      ? 'border-2 border-primary bg-primary-soft text-primary-dark'
                      : 'border border-field-line bg-card'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={on}
                    onChange={() => setTimes((current) => toggleTime(current, time))}
                  />
                  {on && <Icon name="check" className="text-xs" />}
                  {hhmm(time)}
                </label>
              )
            })}
          </div>
          {noTime && (
            <p role="alert" className="mt-2 font-bold text-red-700">
              <Text k="visit_settings.no_time" />
            </p>
          )}
          <p className="mt-3 text-sm text-ink-sub">
            <Text k="visit_settings.kept_note" />
          </p>
        </fieldset>

        <fieldset className="px-4 py-3.5">
          <legend className="float-left w-full font-bold">
            <Icon name="residents" className="mr-2 text-primary" />
            <Text k="visit_settings.daily_limit" />
          </legend>
          <div className="clear-left flex items-center pt-3">
            <span className="inline-flex items-center overflow-hidden rounded-lg border border-field-line">
              <button
                type="button"
                aria-label={stripRuby(t('visit_settings.fewer'))}
                disabled={limit <= DAILY_LIMIT_MIN}
                onClick={() => setLimit((value) => clampDailyLimit(value - 1))}
                className="h-12 w-12 bg-card text-lg disabled:opacity-40"
              >
                <Icon name="minus" />
              </button>
              <span className="flex h-12 min-w-24 items-center justify-center border-x border-card-line px-3 text-lg font-bold">
                <span>
                  <Ruby text={t('visit_settings.groups', { count: limit })} />
                </span>
              </span>
              <button
                type="button"
                aria-label={stripRuby(t('visit_settings.more'))}
                disabled={limit >= DAILY_LIMIT_MAX}
                onClick={() => setLimit((value) => clampDailyLimit(value + 1))}
                className="h-12 w-12 bg-card text-lg disabled:opacity-40"
              >
                <Icon name="plus" />
              </button>
            </span>
          </div>
        </fieldset>
      </div>

      {/* 変えたときだけ、下に保存の帯を出す（開示設定・家族の通知の設定と同じ形。#453） */}
      {(changed || saving || noTime || errorKey) && (
        <div className="fixed inset-x-0 bottom-0 z-10 space-y-1 border-t border-card-line bg-card px-4 py-2.5 shadow-[0_-4px_12px_rgb(15_31_61/0.08)]">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <p className="min-w-0 flex-1 basis-48 text-sm font-bold text-primary-dark">
              {changed && <Text k="visit_settings.unsaved" />}
            </p>
            {changed && (
              <button
                type="button"
                disabled={saving}
                onClick={() => {
                  setTimes(initial.start_times)
                  setLimit(initial.daily_limit)
                }}
                className="min-h-11 rounded-lg border border-primary bg-card px-4 font-bold text-primary-dark disabled:opacity-50"
              >
                <Text k="visit_settings.revert" />
              </button>
            )}
            <button
              type="submit"
              disabled={noTime || saving}
              className="min-h-11 rounded-lg bg-primary px-5 font-bold text-white disabled:opacity-50"
            >
              <Text k={saving ? 'visit_settings.saving' : 'visit_settings.save'} />
            </button>
          </div>
          {errorKey && (
            <p className="text-sm font-bold text-red-700">
              <Text k={errorKey} />
            </p>
          )}
        </div>
      )}
    </form>
  )
}

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
    <section className="space-y-3 rounded-xl border border-card-line bg-card px-4 py-3.5">
      <h2 className="flex flex-wrap items-center gap-x-2 font-bold">
        <Icon name="close" className="text-primary" />
        <Text k="visit_settings.closed_title" />
        {/* 開始時刻・組数と違い、押したらすぐに反映する（今と同じ） */}
        <span className="ml-auto text-xs font-semibold text-ink-sub">
          <Text k="visit_settings.closed_instant" />
        </span>
      </h2>

      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (date && !busy) onClose(date)
        }}
      >
        <label className="text-sm font-bold">
          <Text k="visit_settings.closed_date" />
          <input
            type="date"
            value={date}
            min={today}
            onChange={(event) => setDate(event.target.value)}
            className="mt-1 block min-h-11 rounded-lg border border-field-line bg-card px-3 font-normal"
          />
        </label>
        <button
          type="submit"
          disabled={!date || busy}
          className="min-h-11 rounded-lg border border-primary bg-card px-4 font-bold text-primary-dark disabled:opacity-50"
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
          <span className="font-bold text-red-700">
            <Text k={errorKey} />
          </span>
        ) : (
          notice && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 font-bold text-green-800">
              <Icon name="check" />
              <span>
                <Ruby text={t(notice.key, { count: notice.count })} />
              </span>
            </span>
          )
        )}
      </p>

      {loadErrorKey ? (
        <p className="text-red-700">
          <Text k={loadErrorKey} />
        </p>
      ) : days === null ? null : days.length === 0 ? (
        <p className="text-sm text-ink-sub">
          <Text k="visit_settings.closed_empty" />
        </p>
      ) : (
        <ul className="-mx-4 border-t border-card-line">
          {days.map((day) => (
            <li
              key={day.id}
              className="flex flex-wrap items-center justify-between gap-2 border-b border-card-line px-4 py-2 last:border-b-0"
            >
              <span className="font-bold">
                <Ruby text={formatDate(day.closed_date)} />
              </span>
              <ConfirmButton
                labelKey="visit_settings.open"
                confirmKey="visit_settings.open_confirm"
                disabled={busy}
                onConfirm={() => onOpen(day.id)}
                className="min-h-11 text-sm font-bold text-primary underline"
              />
            </li>
          ))}
        </ul>
      )}
      <p className="text-sm text-ink-sub">
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
  // 2 回押す確かめの状態のあいだは、理由を直せない（確かめた内容と送る内容がずれないように。#317）
  const [armed, setArmed] = useState(false)
  const problem = reasonProblem(reason)

  return (
    <div role="alert" className="space-y-3 rounded-xl border border-amber-300 bg-amber-100 p-3">
      <p className="font-bold">
        <Ruby text={label} />
      </p>
      <p>
        <Ruby text={t('visit_settings.has_reservations', { count: pending.count })} />
      </p>
      <ReasonField
        value={reason}
        onChange={setReason}
        tooLong={problem === 'too_long'}
        locked={armed || busy}
      />
      <div className="flex flex-wrap gap-3">
        <ConfirmButton
          labelKey="visit_settings.confirm_close"
          confirmKey="visit_settings.confirm_close_confirm"
          busyKey="visit_settings.closing"
          busy={busy}
          disabled={problem !== null || busy}
          onConfirm={() => onConfirm(reason)}
          onArmedChange={setArmed}
          className="min-h-11 rounded-lg bg-red-700 px-4 py-2 font-bold text-white disabled:opacity-50"
        />
        <button
          type="button"
          onClick={onDismiss}
          className="min-h-11 text-sm font-bold text-primary underline"
        >
          <Text k="visit_settings.dismiss" />
        </button>
      </div>
    </div>
  )
}
