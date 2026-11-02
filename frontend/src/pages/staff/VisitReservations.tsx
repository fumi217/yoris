import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { ConfirmButton } from '../../components/ConfirmButton'
import { Message } from '../../components/Message'
import { ReasonField } from '../../components/ReasonField'
import { Text } from '../../components/Text'
import { ResidentFamily } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import { changedAtParts } from '../admin/historyRows'
import { reasonProblem } from '../admin/visitSettingsRules'
import { endOf, hhmm, monthDay, todayInJapan, weekdayOf } from '../family/visits/visitDates'
import {
  groupByDate,
  listRange,
  visitsBase,
  VISITS_KEY,
  type StaffReservation,
} from './visitReservationRows'

/**
 * 面会の予約の一覧（UI-S11。spec 003 の T026・T031。職員のすべて）。
 * 職員の画面（/staff/visits）と管理画面（/admin/visits）の両方から開く同じ画面（介護職員・リーダーは管理画面を開けないため）。
 * 今日から 4 週間先までを、日付ごとに時刻の順で出す。取り消したものも状態つきで出す。
 * 予約済みは、理由を入れて 2 回押すと取り消せる（締め切りなし。家族にお知らせとメール。FR-012・FR-013）。
 */
export function VisitReservations() {
  const { pathname } = useLocation()
  const base = visitsBase(pathname)
  const queryClient = useQueryClient()
  const range = listRange(todayInJapan())
  const [notice, setNotice] = useState(false)

  const list = useQuery({
    queryKey: [...VISITS_KEY, 'list', range.from, range.to],
    queryFn: () =>
      api.get<StaffReservation[]>(`/api/admin/visits?from=${range.from}&to=${range.to}`),
  })
  const cancel = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      api.post<StaffReservation>(`/api/admin/visits/${id}/cancel`, { reason: reason.trim() }),
    onMutate: () => setNotice(false),
    onSuccess: () => setNotice(true),
    // 取り消せなかったとき（ほかの職員や家族が先に取り消した 404）も、今の状態を読み直す
    onSettled: () => queryClient.invalidateQueries({ queryKey: VISITS_KEY }),
  })

  return (
    <section className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        <Text k="visit_list.title" />
      </h1>
      <p className="text-sm text-gray-600">
        <Text k="visit_list.range_note" />
      </p>
      <p role="status" aria-live="polite" className="min-h-6 text-sm">
        {cancel.isError ? (
          <span className="text-red-700">
            <Text k={messageKeyOf(cancel.error)} />
          </span>
        ) : (
          notice && <Text k="visit_list.cancelled_notice" />
        )}
      </p>
      {list.isPending ? (
        <Message k="layout.loading" />
      ) : list.isError ? (
        <Message k={messageKeyOf(list.error)} />
      ) : (
        <VisitListView
          rows={list.data}
          cancellingId={cancel.isPending ? cancel.variables.id : null}
          onCancel={(id, reason) => cancel.mutate({ id, reason })}
        />
      )}
      {base === '/staff/visits' && (
        // 管理画面で開いたときは、枠の「管理画面のトップへ」で戻る
        <Link to="/staff" className="inline-block text-primary underline">
          <Text k="visit_list.back_to_residents" />
        </Link>
      )}
    </section>
  )
}

type ListProps = {
  rows: StaffReservation[]
  // 取り消している予約（そのあいだは、ほかの取り消しも押せない）
  cancellingId: number | null
  onCancel: (id: number, reason: string) => void
}

/** 一覧の中身（テストではこれを直接出す）。 */
export function VisitListView({ rows, cancellingId, onCancel }: ListProps) {
  const { t } = useTranslation()
  if (rows.length === 0) return <Message k="visit_list.empty" />

  return (
    <div className="space-y-4">
      {groupByDate(rows).map((group) => (
        <section key={group.date}>
          <h2 className="mb-1 font-bold">
            <Ruby text={dateLabel(t, group.date)} />
          </h2>
          <ul className="divide-y rounded border border-card-line">
            {group.rows.map((row) => (
              <ReservationItem
                key={row.id}
                row={row}
                cancelling={cancellingId === row.id}
                disabled={cancellingId !== null}
                onCancel={onCancel}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

type Translate = ReturnType<typeof useTranslation>['t']

/** 「10月27日（火）」（曜日は家族の画面と同じく、かっこの中に 1 文字）。 */
function dateLabel(t: Translate, date: string): string {
  return t('visit.date', {
    ...monthDay(date),
    weekday: stripRuby(t(`visit.weekday.${weekdayOf(date)}`)),
  })
}

type ItemProps = {
  row: StaffReservation
  cancelling: boolean
  disabled: boolean
  onCancel: (id: number, reason: string) => void
}

function ReservationItem({ row, cancelling, disabled, onCancel }: ItemProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const start = hhmm(row.start_time)
  const active = row.status === 'booked'

  return (
    <li className={`space-y-1 p-3 ${active ? '' : 'text-ink-sub'}`}>
      {/* 時刻・居室・名前の列に決まった幅を付け、「来館者」の開始位置を、行によらずそろえる
          （名前の長さで、あとの列がずれないように）。ふりがなで行の高さが変わっても、文字の下の線をそろえる */}
      <p className="flex flex-wrap items-baseline">
        <span className="w-36 shrink-0 font-bold">
          {t('visit.time_range', { start, end: endOf(start) })}
        </span>
        <span className="w-12 shrink-0 text-gray-600">{row.room}</span>
        <span className="w-80 shrink-0">
          {/* 続柄は出さない：予約したのは代表者だが、来る人が同じとは限らないため（デザインの決めごと 15 章） */}
          <ResidentFamily
            name={row.resident_name}
            ruby={row.resident_name_ruby}
            relationship={null}
          />
        </span>
        {/* 来館する人の数（入居者の人数に見えないよう「来館者」と付ける。#311） */}
        <span>
          <Ruby text={t('visit.visitors', { count: row.party_size })} />
        </span>
      </p>
      <p className="text-sm">
        <Text k={`visit.status.${row.status}`} />
        <span className="ml-3 text-gray-600">
          <Ruby text={t('visit_list.booked_at', changedAtParts(row.created_at))} />
        </span>
      </p>
      {row.cancel_reason && (
        <p className="text-sm">
          <Text k="visit.cancel_reason" />
          {/* 施設が入力した理由は、辞書を通さず文字としてだけ出す（FR-016） */}
          <span className="whitespace-pre-wrap">{row.cancel_reason}</span>
        </p>
      )}
      {active &&
        (open ? (
          <CancelForm
            busy={cancelling}
            disabled={disabled}
            onConfirm={(reason) => onCancel(row.id, reason)}
            onStop={() => setOpen(false)}
          />
        ) : (
          <button
            type="button"
            disabled={disabled}
            onClick={() => setOpen(true)}
            className="rounded border-2 border-field-line px-3 py-1 text-sm disabled:opacity-50"
          >
            <Text k="visit_list.cancel" />
          </button>
        ))}
    </li>
  )
}

type CancelFormProps = {
  busy: boolean
  disabled: boolean
  onConfirm: (reason: string) => void
  onStop: () => void
}

/** 取り消しの理由の入力（必須・200 文字まで。家族の画面に出る）と、2 回押して取り消すボタン。 */
export function CancelForm({ busy, disabled, onConfirm, onStop }: CancelFormProps) {
  const [reason, setReason] = useState('')
  // 2 回押す確かめの状態のあいだは、理由を直せない（確かめた内容と送る内容がずれないように。#317）
  const [armed, setArmed] = useState(false)
  const problem = reasonProblem(reason)

  return (
    <div className="space-y-2 rounded border-2 border-orange-600 bg-orange-50 p-3">
      <ReasonField
        value={reason}
        onChange={setReason}
        tooLong={problem === 'too_long'}
        locked={armed || busy}
      />
      <p className="text-xs text-gray-600">
        <Text k="visit_list.cancel_note" />
      </p>
      <div className="flex flex-wrap gap-3">
        <ConfirmButton
          labelKey="visit_list.cancel_submit"
          confirmKey="visit_list.cancel_confirm"
          busyKey="visit.cancelling"
          busy={busy}
          disabled={problem !== null || disabled}
          onConfirm={() => onConfirm(reason)}
          onArmedChange={setArmed}
          className="rounded bg-orange-700 px-4 py-2 font-bold text-white disabled:opacity-50"
        />
        <button type="button" onClick={onStop} className="text-sm text-gray-700 underline">
          <Text k="visit_list.cancel_stop" />
        </button>
      </div>
    </div>
  )
}
