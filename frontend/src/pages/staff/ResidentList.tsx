import { useQuery } from '@tanstack/react-query'
import { Icon, type IconName } from '../../components/Icon'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { UnconfirmedFlagFilter } from '../../components/change-flags/UnconfirmedFlagFilter'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import {
  dayMarks,
  mealMarks,
  monthDay,
  totalWaitingMessages,
  visibleRows,
  type RecordMark,
  type ResidentListResponse,
  type ResidentRow,
} from './residentRows'
import { useTodayVisits } from './useTodayVisits'
import { bookedCount } from './visitReservationRows'

/**
 * 入居者一覧（UI-S01。spec 001 の T031・spec 004 の T030）。
 * 並びは入居の順（API のまま）。ただし、変化の目印の付いた入居者を先に並べる（spec 006 の 006-T015）。
 * 今日の未記録・返事待ち・家族からのメッセージの件数が分かる。
 * 通知・音は出さない。開いたとき（画面に戻ったとき）に読み直す（docs/画面設計.md「4」）。
 */
export function ResidentList() {
  const residents = useQuery({
    queryKey: ['staff', 'residents'],
    queryFn: () => api.get<ResidentListResponse>('/api/staff/residents'),
  })

  // 今日の面会の組数（読めないときは出さない。一覧は使えるように）
  const visits = useTodayVisits()

  if (residents.isPending) return <Message k="layout.loading" />
  if (residents.isError) return <Message k={messageKeyOf(residents.error)} />
  return (
    <ResidentTable
      data={residents.data}
      todayVisits={visits.data ? bookedCount(visits.data) : null}
    />
  )
}

/** 一覧の中身（API の結果をそのまま並べる。テストではこれを直接出す）。 */
export function ResidentTable({
  data,
  todayVisits = null,
}: {
  data: ResidentListResponse
  // 今日の面会の組数。まだ読めていない・読めないときは null（出さない）
  todayVisits?: number | null
}) {
  const { t } = useTranslation()
  const messages = totalWaitingMessages(data.residents)
  // 「確かめていない目印」で絞っているか（spec 006 の FR-003。もう一度押すと全員に戻す）
  const [onlyUnconfirmed, setOnlyUnconfirmed] = useState(false)
  const rows = visibleRows(data.residents, onlyUnconfirmed)

  return (
    <section>
      <div className="space-y-3 p-4">
        <h1 className="text-xl font-bold">
          <Text k="resident_list.title" />
          <span className="ml-3 text-base font-normal">
            <Ruby text={t('resident_list.date', monthDay(data.date))} />
          </span>
        </h1>
        {/* 日付の下に、横 1 列で「確かめていない目印」・メッセージ・面会（docs/画面設計.md「4」） */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <UnconfirmedFlagFilter
            count={data.unconfirmed_flag_count}
            active={onlyUnconfirmed}
            onToggle={() => setOnlyUnconfirmed((value) => !value)}
          />
          {/* 押すと、家族からのメッセージの一覧（UI-S08。spec 004 の T029）へ進む */}
          <Link to="/staff/messages" className="text-primary underline">
            <Ruby text={t('resident_list.messages_total', { count: messages })} />
          </Link>
          {todayVisits !== null && (
            // 押すと、今日の面会予定（UI-S12。spec 003 の T027）へ進む。0 組でも出す
            <Link to="/staff/visits/today" className="text-primary underline">
              <Ruby text={t('resident_list.today_visits', { count: todayVisits })} />
            </Link>
          )}
        </div>
      </div>
      <p className="px-4 pb-2 text-xs text-gray-600">
        <Icon name="check" className="mr-1" />
        <Text k="resident_list.legend" />
      </p>
      {data.residents.length === 0 ? (
        <Message k="resident_list.empty" />
      ) : (
        <ul className="divide-y border-t">
          {rows.map((row) => (
            <ResidentItem key={row.id} row={row} />
          ))}
        </ul>
      )}
    </section>
  )
}

function ResidentItem({ row }: { row: ResidentRow }) {
  const { t } = useTranslation()

  return (
    // 行の大部分は記録の画面へのリンク。📩 だけは、その入居者の家族からのメッセージの一覧への
    // 別のリンクにする（リンクの中にリンクは置けないため、横に並べる。#241）
    <li className="flex items-stretch hover:bg-gray-50">
      <Link
        to={`/staff/residents/${row.id}`}
        className="flex flex-1 flex-wrap items-center justify-between gap-x-4 gap-y-2 p-4"
      >
        <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="w-10 text-sm text-gray-600">{row.room}</span>
          {/* 入居者の呼び名は、辞書を通さずそのまま出す */}
          <span className="font-bold">{row.display_name}</span>
          {row.change_flag && (
            // 右の件数の列に入れると見落としやすいので、呼び名のすぐ横に置く（docs/画面設計.md「4」）
            <span className="text-sm font-bold text-amber-800">
              <Icon name="warning" className="mr-1" />
              <Text k="change.title" />
            </span>
          )}
        </span>
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span>
            <Icon name="meal" className="mr-1" />
            <Marks marks={mealMarks(row)} />
          </span>
          <Marks marks={dayMarks(row)} />
          {/* 返事待ちの欄は、ないときも幅を取る（印の列が、行によって右にずれないように） */}
          <span className="inline-block min-w-12">
            {row.waiting_requests > 0 && (
              <Count
                icon="request-waiting"
                count={row.waiting_requests}
                label={t('resident_list.waiting_requests', { count: row.waiting_requests })}
              />
            )}
          </span>
        </span>
      </Link>
      {row.waiting_messages > 0 && (
        <Link
          to={`/staff/messages?resident_id=${row.id}`}
          className="flex items-center px-4 text-sm text-primary"
        >
          <Count
            icon="family-message"
            count={row.waiting_messages}
            label={t('resident_list.waiting_messages', { count: row.waiting_messages })}
          />
        </Link>
      )}
    </li>
  )
}

/** 「朝 ✔ 昼 ・」の並び。✔・ は読み上げでは「記録済み」「まだ記録していません」と読む。 */
function Marks({ marks }: { marks: RecordMark[] }) {
  const { t } = useTranslation()

  return (
    // 文字のふりがなの有無（「おやつ」は読みが付かない）で、行の高さが違っても、文字の基準線をそろえる
    <span className="inline-flex items-baseline gap-2">
      {marks.map((mark) => (
        <span
          key={mark.labelKey}
          className={mark.recorded || mark.optional ? '' : 'font-bold text-orange-700'}
        >
          <Text k={mark.labelKey} />
          {/* ✔ と ・ で幅が違うので、同じ幅の枠に入れて、中央にそろえる */}
          <span aria-hidden="true" className="ml-1 inline-block w-4 text-center">
            {mark.recorded ? <Icon name="check" /> : '・'}
          </span>
          <span className="sr-only">
            {stripRuby(t(mark.recorded ? 'resident_list.recorded' : 'resident_list.not_recorded'))}
          </span>
        </span>
      ))}
    </span>
  )
}

function Count({ icon, count, label }: { icon: IconName; count: number; label: string }) {
  return (
    <span title={stripRuby(label)}>
      <span aria-hidden="true">
        <Icon name={icon} className="mr-1" />
        {count}
      </span>
      <span className="sr-only">{stripRuby(label)}</span>
    </span>
  )
}
