import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { Icon } from '../../components/Icon'
import { messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentFamily } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import { endOf, hhmm } from '../family/visits/visitDates'
import { useTodayVisits } from './useTodayVisits'
import { type StaffReservation } from './visitReservationRows'

/**
 * 今日の面会予定（UI-S12。spec 003 の T027。`/staff/visits/today`）。
 * 今日（日本時間）の予約済みを、時刻の順に出す（API が並べる）。取り消しは、予約の一覧（UI-S11）から行う。
 */
export function TodayVisits() {
  const today = useTodayVisits()

  return (
    <section className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">
        <Text k="visit_list.today_title" />
      </h1>
      {today.isPending ? (
        <Message k="layout.loading" />
      ) : today.isError ? (
        <Message k={messageKeyOf(today.error)} />
      ) : (
        <TodayVisitsView rows={today.data} />
      )}
      {/* 予約の一覧（UI-S11。取り消しはここから）への入口（#443） */}
      <Link
        to="/staff/visits"
        className="flex min-h-14 items-center gap-3 rounded-2xl border border-card-line bg-card px-4 py-2.5 font-bold text-primary-dark hover:bg-primary-soft"
      >
        <Icon name="visit-list" className="text-lg" />
        <span className="flex-1">
          <Text k="visit_list.to_list" />
        </span>
        <Icon name="next" className="text-ink-sub" />
      </Link>
      <Link
        to="/staff"
        className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary"
      >
        <Icon name="prev" />
        <Text k="visit_list.back_to_residents" />
      </Link>
    </section>
  )
}

/** 今日の予定の中身（テストではこれを直接出す）。 */
export function TodayVisitsView({ rows }: { rows: StaffReservation[] }) {
  const { t } = useTranslation()
  if (rows.length === 0) return <Message k="visit_list.today_empty" />

  return (
    <ol className="overflow-hidden rounded-2xl border border-card-line bg-card">
      {rows.map((row) => {
        const start = hhmm(row.start_time)
        return (
          <li
            key={row.id}
            className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-card-line px-4 py-3 first:border-t-0"
          >
            {/* 時刻を大きく（いつ来るかが、まず目に入るように。#443） */}
            <span className="flex w-20 shrink-0 flex-col leading-tight">
              <span className="text-2xl font-bold tabular-nums">{start}</span>
              <span className="text-sm text-ink-sub tabular-nums">〜{endOf(start)}</span>
            </span>
            <RoomTile room={row.room} />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="text-lg font-bold">
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
              </span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

/** 居室の札（入居者一覧・記録の画面と同じ形）。予約の一覧でも使う。 */
export function RoomTile({ room }: { room: string }) {
  return (
    <span className="flex w-13 shrink-0 flex-col items-center rounded-xl bg-page py-1 leading-tight">
      <span className="text-xs font-bold text-ink-sub">
        <Text k="resident_list.room" />
      </span>
      <span className="text-lg font-bold">{room}</span>
    </span>
  )
}
