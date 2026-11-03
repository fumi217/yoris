import { useQuery } from '@tanstack/react-query'
import { Icon, type IconName } from '../../components/Icon'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { UnconfirmedFlagFilter } from '../../components/change-flags/UnconfirmedFlagFilter'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentName } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import {
  monthDay,
  recordChips,
  recordProgress,
  showCautionSection,
  splitByFlag,
  totalWaitingMessages,
  visibleRows,
  type RecordMark,
  type ResidentListResponse,
  type ResidentRow,
} from './residentRows'
import { useMemoApprovalCount } from './useMemoApprovalCount'
import { useTodayVisits } from './useTodayVisits'
import { bookedCount } from './visitReservationRows'

/**
 * 入居者一覧（UI-S01。spec 001 の T031・spec 004 の T030）。
 * 並びは入居の順（API のまま）。ただし、変化の目印の付いた入居者を先に並べる（spec 006 の 006-T015）。
 * 今日の未記録・返事待ち・家族からのメッセージの件数が分かる。
 * 通知・音は出さない。開いたとき（画面に戻ったとき）に読み直す（docs/画面設計.md「4」）。
 * 見た目（#431。デザインの決めごと 11.4）：上に今日の進み具合、変化の目印のある人を「気をつけたい人」にまとめ、
 * 記録の状態はチップ（記録済みは緑と ✔、まだは点線と －）で示す。機能・API は変えていない。
 */
export function ResidentList() {
  const residents = useQuery({
    queryKey: ['staff', 'residents'],
    queryFn: () => api.get<ResidentListResponse>('/api/staff/residents'),
  })

  // 今日の面会の組数（読めないときは出さない。一覧は使えるように）
  const visits = useTodayVisits()
  // 様子のメモの承認待ち（リーダー・施設長だけ。承認できない人・読めないときは null で、出さない）
  const memoApprovals = useMemoApprovalCount()

  if (residents.isPending) return <Message k="layout.loading" />
  if (residents.isError) return <Message k={messageKeyOf(residents.error)} />
  return (
    <ResidentTable
      data={residents.data}
      todayVisits={visits.data ? bookedCount(visits.data) : null}
      memoApprovals={memoApprovals}
    />
  )
}

/** 一覧の中身（API の結果をそのまま並べる。テストではこれを直接出す）。 */
export function ResidentTable({
  data,
  todayVisits = null,
  memoApprovals = null,
}: {
  data: ResidentListResponse
  // 今日の面会の組数。まだ読めていない・読めないときは null（出さない）
  todayVisits?: number | null
  // 様子のメモの承認待ちの件数。承認できない人・まだ読めない・読めないときは null（出さない）
  memoApprovals?: number | null
}) {
  const { t } = useTranslation()
  const messages = totalWaitingMessages(data.residents)
  // 「確かめていない目印」で絞っているか（spec 006 の FR-003。もう一度押すと全員に戻す）
  const [onlyUnconfirmed, setOnlyUnconfirmed] = useState(false)
  const { caution, others } = splitByFlag(visibleRows(data.residents, onlyUnconfirmed))

  return (
    <section className="space-y-4 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h1 className="text-2xl font-bold">
          <Text k="resident_list.title" />
        </h1>
        <span className="text-base font-semibold text-ink-sub">
          <Ruby text={t('resident_list.date', monthDay(data.date))} />
        </span>
      </div>
      <TodaySummary
        residents={data.residents}
        messages={messages}
        todayVisits={todayVisits}
        memoApprovals={memoApprovals}
      />
      {data.residents.length === 0 ? (
        <Message k="resident_list.empty" />
      ) : (
        <>
          {showCautionSection(caution.length, data.unconfirmed_flag_count, onlyUnconfirmed) && (
            <section aria-labelledby="residents-caution">
              <div className="mb-2 ml-1 flex flex-wrap items-center justify-between gap-2">
                {/* アイコンと文字は、flex に入れず 1 つの行（インライン）にする：flex だと、ふりがなを含めた
                    高さの中央にアイコンが置かれ、文字より上に浮いて見える（AlbumUpload のボタンと同じ。#390） */}
                <h2 id="residents-caution" className="font-bold">
                  <Icon name="warning" className="mr-2 text-amber-800" />
                  <Text k="resident_list.caution_title" />
                  <span className="ml-2 text-sm font-bold text-ink-sub">
                    <Ruby text={t('resident_list.people', { count: caution.length })} />
                  </span>
                </h2>
                <UnconfirmedFlagFilter
                  count={data.unconfirmed_flag_count}
                  active={onlyUnconfirmed}
                  onToggle={() => setOnlyUnconfirmed((value) => !value)}
                />
              </div>
              <ul className="overflow-hidden rounded-2xl border border-amber-300 bg-card">
                {caution.map((row) => (
                  <ResidentItem key={row.id} row={row} flagged />
                ))}
              </ul>
            </section>
          )}
          {others.length > 0 && (
            <section aria-labelledby="residents-others">
              <h2 id="residents-others" className="mb-2 ml-1 font-bold">
                <Text k="resident_list.others_title" />
                <span className="ml-2 text-sm font-bold text-ink-sub">
                  <Ruby text={t('resident_list.people', { count: others.length })} />
                </span>
              </h2>
              <ul className="overflow-hidden rounded-2xl border border-card-line bg-card">
                {others.map((row) => (
                  <ResidentItem key={row.id} row={row} />
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </section>
  )
}

/** 一番上の白い面：今日の記録の進み具合と、家族からのメッセージ・今日の面会の件数（押すと、それぞれの画面へ）。 */
function TodaySummary({
  residents,
  messages,
  todayVisits,
  memoApprovals,
}: {
  residents: ResidentRow[]
  messages: number
  todayVisits: number | null
  memoApprovals: number | null
}) {
  const { t } = useTranslation()
  const { recorded, total } = recordProgress(residents)
  const left = total - recorded
  const countText = t('resident_list.today_record_count', { done: recorded, total })
  const percent = total === 0 ? 0 : Math.round((recorded / total) * 100)
  return (
    <div
      className={`grid gap-4 rounded-2xl border border-card-line bg-card p-4 sm:items-center sm:gap-6 ${
        residents.length > 0 ? 'sm:grid-cols-[1.3fr_1fr]' : ''
      }`}
    >
      {residents.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-bold text-ink-sub">
            <Text k="resident_list.today_record" />
          </h2>
          <p className="text-3xl font-extrabold leading-none">
            <Ruby text={countText} />
          </p>
          {/* 棒は飾りに近い：数字と文を文字で出している。読み上げ用に値も付ける（1.4.11・4.1.2） */}
          <div
            role="progressbar"
            aria-label={`${stripRuby(t('resident_list.today_record'))} ${stripRuby(countText)}`}
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={recorded}
            className="mt-3 h-3 overflow-hidden rounded-full bg-card-line"
          >
            <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
          </div>
          <p className="mt-2 text-sm text-ink-sub">
            <Ruby
              text={t(
                left === 0 ? 'resident_list.today_record_done' : 'resident_list.today_record_left',
                {
                  count: left,
                },
              )}
            />
          </p>
        </div>
      )}
      <div className="flex flex-col gap-2">
        {/* 押すと、家族からのメッセージの一覧（UI-S08。spec 004 の T029）へ進む */}
        <SummaryLink
          to="/staff/messages"
          icon="family-message"
          labelKey="resident_list.summary_messages"
          count={messages}
          unitKey="resident_list.unit_cases"
        />
        {todayVisits !== null && (
          // 押すと、今日の面会予定（UI-S12。spec 003 の T027）へ進む。0 組でも出す
          <SummaryLink
            to="/staff/visits/today"
            icon="visits"
            labelKey="resident_list.summary_visits"
            count={todayVisits}
            unitKey="resident_list.unit_groups"
          />
        )}
        {memoApprovals !== null && (
          // 押すと、様子のメモの承認の画面（UI-S07。spec 007 の T023）へ進む。0 件でも出す
          <SummaryLink
            to="/staff/memo-approvals"
            icon="memo"
            labelKey="resident_list.summary_memo_approvals"
            count={memoApprovals}
            unitKey="resident_list.unit_cases"
          />
        )}
      </div>
    </div>
  )
}

function SummaryLink({
  to,
  icon,
  labelKey,
  count,
  unitKey,
}: {
  to: string
  icon: IconName
  labelKey: string
  count: number
  unitKey: string
}) {
  return (
    <Link
      to={to}
      className="flex min-h-14 items-center gap-3 rounded-xl bg-page px-3 py-2 hover:bg-primary-soft"
    >
      <span
        aria-hidden="true"
        className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary"
      >
        <Icon name={icon} />
      </span>
      <span className="min-w-0 flex-1 text-sm text-ink-sub">
        <Text k={labelKey} />
      </span>
      <span className="text-xl font-extrabold">
        {count}
        <small className="ml-0.5 text-sm font-semibold">
          <Text k={unitKey} />
        </small>
      </span>
      <Icon name="next" className="shrink-0 text-ink-sub" />
    </Link>
  )
}

function ResidentItem({ row, flagged = false }: { row: ResidentRow; flagged?: boolean }) {
  const { t } = useTranslation()

  return (
    // 行の大部分は記録の画面へのリンク。メッセージの件数だけは、その入居者の家族からのメッセージの一覧への
    // 別のリンクにする（リンクの中にリンクは置けないため、横に並べる。#241）
    <li
      className={`flex items-stretch border-t first:border-t-0 ${flagged ? 'border-amber-300' : ''}`}
    >
      <Link
        to={`/staff/residents/${row.id}`}
        // 広い幅：左に居室、真ん中に名前とチップ、右に件数と矢印。狭い幅（320px）：チップは下の全幅に出す
        // （名前の横に置くと、1 つずつ縦に積まれて、行がとても高くなる）
        className={`grid min-h-20 min-w-0 flex-1 grid-cols-[3.5rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 py-3 pl-3 pr-2 ${
          flagged ? 'bg-amber-100 hover:bg-amber-200' : 'hover:bg-primary-soft'
        }`}
      >
        <span className="flex flex-col items-center rounded-xl bg-page py-1 leading-tight sm:row-span-2">
          <span className="text-xs font-bold text-ink-sub">
            <Text k="resident_list.room" />
          </span>
          <span className="text-lg font-bold">{row.room}</span>
        </span>
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          {/* 一覧は文字が多くなるので、「さん」は付けない（docs/デザインの決めごと.md の 15 章） */}
          <span className="text-lg font-bold">
            <ResidentName name={row.display_name} ruby={row.display_name_ruby} honorific={false} />
          </span>
          {row.change_flag && (
            // 名前のすぐ横に置く（右の件数の列に入れると見落としやすい。docs/画面設計.md「4」）
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-800 bg-white px-2.5 py-0.5 text-xs font-bold text-amber-800 whitespace-nowrap">
              <Icon name="warning" />
              <Text k="change.title" />
            </span>
          )}
        </span>
        <span className="flex shrink-0 items-center gap-2 sm:row-span-2">
          {row.waiting_requests > 0 && (
            <Count
              icon="request-waiting"
              count={row.waiting_requests}
              label={t('resident_list.waiting_requests', { count: row.waiting_requests })}
              className="bg-red-100 text-red-800"
            />
          )}
          <Icon name="next" className="text-ink-sub" />
        </span>
        <span className="col-span-3 flex flex-wrap gap-1.5 sm:col-span-1">
          {recordChips(row).map((mark) => (
            <RecordChip key={mark.labelKey} mark={mark} />
          ))}
        </span>
      </Link>
      {row.waiting_messages > 0 && (
        <Link
          to={`/staff/messages?resident_id=${row.id}`}
          className={`flex min-w-12 items-center justify-center px-2 text-sm ${
            flagged ? 'bg-amber-100 hover:bg-amber-200' : 'hover:bg-primary-soft'
          }`}
        >
          <Count
            icon="family-message"
            count={row.waiting_messages}
            label={t('resident_list.waiting_messages', { count: row.waiting_messages })}
            className="bg-primary-soft text-primary-dark"
          />
        </Link>
      )}
    </li>
  )
}

/**
 * 記録のチップ：記録済みは緑と ✔、まだは点線の枠と －。色だけに頼らない（1.4.1）。
 * 読み上げは「朝 記録済み」「朝 まだ記録していません」（✔・－ は飾り）。
 */
function RecordChip({ mark }: { mark: RecordMark }) {
  const { t } = useTranslation()
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1 rounded-full px-2.5 text-sm ${
        mark.recorded
          ? 'bg-green-100 font-bold text-green-800'
          : 'border border-dashed border-field-line bg-card text-ink-sub'
      }`}
    >
      <Text k={mark.labelKey} />
      <Icon name={mark.recorded ? 'check' : 'minus'} className="text-xs" />
      <span className="sr-only">
        {stripRuby(t(mark.recorded ? 'resident_list.recorded' : 'resident_list.not_recorded'))}
      </span>
    </span>
  )
}

function Count({
  icon,
  count,
  label,
  className,
}: {
  icon: IconName
  count: number
  label: string
  className: string
}) {
  return (
    <span
      title={stripRuby(label)}
      className={`inline-flex min-h-7 items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-sm font-bold ${className}`}
    >
      <span aria-hidden="true">
        <Icon name={icon} className="mr-1" />
        {count}
      </span>
      <span className="sr-only">{stripRuby(label)}</span>
    </span>
  )
}
