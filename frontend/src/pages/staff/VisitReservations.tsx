import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { ConfirmButton } from '../../components/ConfirmButton'
import { Icon } from '../../components/Icon'
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
import { RoomTile } from './TodayVisits'

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
      <h1 className="text-2xl font-bold">
        <Text k="visit_list.title" />
      </h1>
      <p className="text-sm text-ink-sub">
        <Text k="visit_list.range_note" />
      </p>
      <p role="status" aria-live="polite" className="min-h-6 text-sm">
        {cancel.isError ? (
          <span className="font-bold text-red-700">
            <Text k={messageKeyOf(cancel.error)} />
          </span>
        ) : (
          notice && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 font-bold text-green-800">
              <Icon name="check" />
              <Text k="visit_list.cancelled_notice" />
            </span>
          )
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
        <Link
          to="/staff"
          className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary"
        >
          <Icon name="prev" />
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
  const today = todayInJapan()
  if (rows.length === 0) return <Message k="visit_list.empty" />

  return (
    <div className="space-y-4">
      {groupByDate(rows).map((group) => (
        <section key={group.date} className="space-y-2">
          <h2 className="ml-1 flex items-center gap-2 font-bold text-ink-sub">
            {/* Ruby は枠を作らず文字の断片を並べるので、span で 1 つの部品にする
                （flex の中で断片がばらばらに並び、間があいて高さもずれないように。PR #446 ようこさん） */}
            <span>
              <Ruby text={dateLabel(t, group.date)} />
            </span>
            {group.date === today && (
              <span className="rounded-full bg-primary px-2.5 py-0.5 text-xs text-white">
                <Text k="visit_list.today_mark" />
              </span>
            )}
          </h2>
          <ul className="overflow-hidden rounded-2xl border border-card-line bg-card">
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
    <li className="space-y-2 border-t border-card-line px-4 py-3 first:border-t-0">
      {/* 1 段目：時刻・状態・取り消す。2 段目：居室の札・名前・来館者（狭い幅でも名前が細く折れないように。#443） */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {/* 取り消した予約は、薄く（取り消し線）して、状態のラベルの文字でも示す（色だけに頼らない） */}
        <span className={`tabular-nums ${active ? '' : 'text-ink-sub line-through'}`}>
          <span className="text-xl font-bold">{start}</span>
          <span className="ml-1 text-sm text-ink-sub">〜{endOf(start)}</span>
        </span>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-bold whitespace-nowrap ${
            active ? 'bg-green-100 text-green-800' : 'border border-card-line bg-page text-ink-sub'
          }`}
        >
          <Text k={`visit.status.${row.status}`} />
        </span>
        {active && !open && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => setOpen(true)}
            className="ml-auto inline-flex min-h-11 items-center gap-1 rounded-full border border-field-line bg-card px-4 text-sm font-semibold disabled:opacity-50"
          >
            <Icon name="close" />
            <Text k="visit_list.cancel" />
          </button>
        )}
      </div>
      <div className="flex items-center gap-3">
        <RoomTile room={row.room} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className={`text-lg font-bold ${active ? '' : 'text-ink-sub'}`}>
            {/* 続柄は出さない：予約したのは代表者だが、来る人が同じとは限らないため（デザインの決めごと 15 章） */}
            <ResidentFamily
              name={row.resident_name}
              ruby={row.resident_name_ruby}
              relationship={null}
            />
          </span>
          {/* 来館する人の数（入居者の人数に見えないよう「来館者」と付ける。#311） */}
          <span className="text-sm text-ink-sub">
            <Ruby text={t('visit.visitors', { count: row.party_size })} />
            <span className="ml-3 inline-block">
              <Ruby text={t('visit_list.booked_at', changedAtParts(row.created_at))} />
            </span>
          </span>
        </span>
      </div>
      {row.cancel_reason && (
        <p className="text-sm text-ink-sub">
          <Text k="visit.cancel_reason" />
          {/* 施設が入力した理由は、辞書を通さず文字としてだけ出す（FR-016） */}
          <span className="whitespace-pre-wrap">{row.cancel_reason}</span>
        </p>
      )}
      {active && open && (
        <CancelForm
          busy={cancelling}
          disabled={disabled}
          onConfirm={(reason) => onCancel(row.id, reason)}
          onStop={() => setOpen(false)}
        />
      )}
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
    <div className="space-y-2 rounded-2xl border border-amber-300 bg-amber-100 p-3">
      <ReasonField
        value={reason}
        onChange={setReason}
        tooLong={problem === 'too_long'}
        locked={armed || busy}
      />
      <p className="text-sm text-ink-sub">
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
          className="min-h-12 rounded-2xl bg-red-700 px-5 py-2 font-bold text-white disabled:opacity-50"
        />
        <button
          type="button"
          onClick={onStop}
          className="min-h-11 text-sm font-bold text-primary underline"
        >
          <Text k="visit_list.cancel_stop" />
        </button>
      </div>
    </div>
  )
}
