import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import {
  dayMarks,
  mealMarks,
  monthDay,
  totalWaitingMessages,
  type RecordMark,
  type ResidentListResponse,
  type ResidentRow,
} from './residentRows'

/**
 * 入居者一覧（UI-S01。spec 001 の T031・spec 004 の T030）。
 * 並びは入居の順（API のまま）。今日の未記録・返事待ち・家族からのメッセージの件数が分かる。
 * 通知・音は出さない。開いたとき（画面に戻ったとき）に読み直す（docs/画面設計.md「4」）。
 */
export function ResidentList() {
  const residents = useQuery({
    queryKey: ['staff', 'residents'],
    queryFn: () => api.get<ResidentListResponse>('/api/staff/residents'),
  })

  if (residents.isPending) return <Message k="layout.loading" />
  if (residents.isError) return <Message k={messageKeyOf(residents.error)} />
  return <ResidentTable data={residents.data} />
}

/** 一覧の中身（API の結果をそのまま並べる。テストではこれを直接出す）。 */
export function ResidentTable({ data }: { data: ResidentListResponse }) {
  const { t } = useTranslation()
  const messages = totalWaitingMessages(data.residents)

  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-2 p-4">
        <h1 className="text-xl font-bold">
          <Text k="resident_list.title" />
          <span className="ml-3 text-base font-normal">
            <Ruby text={t('resident_list.date', monthDay(data.date))} />
          </span>
        </h1>
        {/* 押すと、家族からのメッセージの一覧（UI-S08。spec 004 の T029）へ進む */}
        <p className="text-sm">
          <Link to="/staff/messages" className="text-sky-700 underline">
            <Ruby text={t('resident_list.messages_total', { count: messages })} />
          </Link>
        </p>
      </div>
      <p className="px-4 pb-2 text-xs text-gray-600">
        <Text k="resident_list.legend" />
      </p>
      {data.residents.length === 0 ? (
        <Message k="resident_list.empty" />
      ) : (
        <ul className="divide-y border-t">
          {data.residents.map((row) => (
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
    <li>
      <Link
        to={`/staff/residents/${row.id}`}
        className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 p-4 hover:bg-gray-50"
      >
        <span className="flex items-baseline gap-3">
          <span className="w-10 text-sm text-gray-600">{row.room}</span>
          {/* 入居者の呼び名は、辞書を通さずそのまま出す */}
          <span className="font-bold">{row.display_name}</span>
        </span>
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span>
            <span aria-hidden="true">🍚 </span>
            <Marks marks={mealMarks(row)} />
          </span>
          <Marks marks={dayMarks(row)} />
          {row.waiting_requests > 0 && (
            <Count
              icon="💬"
              count={row.waiting_requests}
              label={t('resident_list.waiting_requests', { count: row.waiting_requests })}
            />
          )}
          {row.waiting_messages > 0 && (
            <Count
              icon="📩"
              count={row.waiting_messages}
              label={t('resident_list.waiting_messages', { count: row.waiting_messages })}
            />
          )}
        </span>
      </Link>
    </li>
  )
}

/** 「朝 ✔ 昼 ・」の並び。✔・ は読み上げでは「記録済み」「まだ記録していません」と読む。 */
function Marks({ marks }: { marks: RecordMark[] }) {
  const { t } = useTranslation()

  return (
    <span className="inline-flex gap-2">
      {marks.map((mark) => (
        <span
          key={mark.labelKey}
          className={mark.recorded || mark.optional ? '' : 'font-bold text-orange-700'}
        >
          <Text k={mark.labelKey} />
          <span aria-hidden="true"> {mark.recorded ? '✔' : '・'}</span>
          <span className="sr-only">
            {stripRuby(t(mark.recorded ? 'resident_list.recorded' : 'resident_list.not_recorded'))}
          </span>
        </span>
      ))}
    </span>
  )
}

function Count({ icon, count, label }: { icon: string; count: number; label: string }) {
  return (
    <span title={stripRuby(label)}>
      <span aria-hidden="true">
        {icon} {count}
      </span>
      <span className="sr-only">{stripRuby(label)}</span>
    </span>
  )
}
