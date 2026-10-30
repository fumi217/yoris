import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
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
      <h1 className="text-xl font-bold">
        <Text k="visit_list.today_title" />
      </h1>
      {today.isPending ? (
        <Message k="layout.loading" />
      ) : today.isError ? (
        <Message k={messageKeyOf(today.error)} />
      ) : (
        <TodayVisitsView rows={today.data} />
      )}
      <div className="flex flex-wrap gap-4 text-primary underline">
        <Link to="/staff/visits">
          <Text k="visit_list.to_list" />
        </Link>
        <Link to="/staff">
          <Text k="visit_list.back_to_residents" />
        </Link>
      </div>
    </section>
  )
}

/** 今日の予定の中身（テストではこれを直接出す）。 */
export function TodayVisitsView({ rows }: { rows: StaffReservation[] }) {
  const { t } = useTranslation()
  if (rows.length === 0) return <Message k="visit_list.today_empty" />

  return (
    <ul className="divide-y rounded border border-card-line">
      {rows.map((row) => {
        const start = hhmm(row.start_time)
        return (
          <li key={row.id} className="p-3">
            <span className="mr-3 text-lg font-bold">
              {t('visit.time_range', { start, end: endOf(start) })}
            </span>
            <span className="mr-2 text-gray-600">{row.room}</span>
            {/* 入居者の呼び名は、辞書を通さずそのまま出す */}
            <span className="mr-3">{row.resident_name}</span>
            {/* 来館する人の数（入居者の人数に見えないよう「来館者」と付ける。#311） */}
            <Ruby text={t('visit.visitors', { count: row.party_size })} />
          </li>
        )
      })}
    </ul>
  )
}
