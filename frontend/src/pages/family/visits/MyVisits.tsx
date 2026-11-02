import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../../api/client'
import { ConfirmButton } from '../../../components/ConfirmButton'
import { StatusBadge } from '../../../components/StatusBadge'
import { Text } from '../../../components/Text'
import { Ruby } from '../../../i18n/Ruby'
import { stripRuby } from '../../../i18n/rubyText'
import { DateChip } from './DateChip'
import { endOf, hhmm, monthDay, MY_VISITS_KEY, weekdayOf, type MyReservation } from './visitDates'

/**
 * 自分の予約（spec 003 の T018。面会の予約の画面のいちばん上に出す。docs/画面設計.md の UI-F01）。
 * これからの予約を日時・人数・状態とともに出し、前日 17 時までなら取り消せる（FR-006・FR-007）。
 * 押し間違えないよう、取り消しは 2 回押す（ConfirmButton。1 回目で「やめる」も出て、「やめる」か 2 回目を押すまで残る）。取り消すと、その時間がまた選べる（空きを読み直す）。
 * 「これからの予約」を読めたら、面会のお知らせ（確定・取り消し・前日の知らせ）を読んだことにする（#272）。
 */
export function MyVisits() {
  const queryClient = useQueryClient()
  const [notice, setNotice] = useState(false)
  const mine = useQuery({
    queryKey: MY_VISITS_KEY,
    queryFn: () => api.get<MyReservation[]>('/api/family/visits'),
  })
  // 面会のお知らせを読んだことにして、お知らせの一覧の「new」を読み直す（画面を開いたときに 1 回だけ）
  const readNotices = useMutation({
    mutationFn: () => api.post('/api/family/visits/notices/read'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['family', 'notifications'] }),
  })
  const noticesRead = useRef(false)
  const { mutate: markRead } = readNotices
  // 前に開いたときの一覧が残っていても、この画面で読み直せてから呼ぶ（読み直す前に届いた
  // 取り消しなどのお知らせを、中身を見る前に読んだことにしない。PR #273 さとこ）
  useEffect(() => {
    if (mine.isSuccess && mine.isFetchedAfterMount && !noticesRead.current) {
      noticesRead.current = true
      markRead()
    }
  }, [mine.isSuccess, mine.isFetchedAfterMount, markRead])
  const cancel = useMutation({
    mutationFn: (id: number) => api.delete(`/api/family/visits/${id}`),
    onSuccess: () => setNotice(true),
    // 締め切りを過ぎていた（409）ときも、今の状態を読み直す
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: MY_VISITS_KEY }),
        queryClient.invalidateQueries({ queryKey: ['family', 'visits', 'availability'] }),
      ]),
  })

  if (mine.isPending) return null
  // 読めないときは、予約の画面のほうは使えるよう、この欄だけ短く知らせる（PR #218 さとこ）
  if (mine.isError) {
    return (
      <p className="text-sm text-gray-600">
        <Text k="visit.mine_error" />
      </p>
    )
  }
  return (
    <MyVisitsView
      rows={mine.data}
      cancellingId={cancel.isPending ? cancel.variables : null}
      notice={notice}
      errorKey={cancel.isError ? messageKeyOf(cancel.error) : null}
      onCancel={(id) => {
        setNotice(false)
        cancel.mutate(id)
      }}
    />
  )
}

type ViewProps = {
  rows: MyReservation[]
  cancellingId: number | null
  notice: boolean
  errorKey: string | null
  onCancel: (id: number) => void
}

/** 欄の中身（テストではこれを直接出す）。 */
export function MyVisitsView({ rows, cancellingId, notice, errorKey, onCancel }: ViewProps) {
  return (
    <section className="space-y-2">
      <h2 className="ml-1 text-sm font-bold text-ink-sub">
        <Text k="visit.mine_title" />
      </h2>
      {errorKey && (
        <p role="alert" className="text-red-700">
          <Text k={errorKey} />
        </p>
      )}
      {notice && !errorKey && (
        <p role="status">
          <Text k="visit.cancelled_notice" />
        </p>
      )}
      {rows.length === 0 ? (
        <p className="rounded-2xl border border-card-line bg-card p-4 text-sm text-ink-sub">
          <Text k="visit.mine_empty" />
        </p>
      ) : (
        <ul className="overflow-hidden rounded-2xl border border-card-line bg-card">
          {rows.map((row) => (
            <ReservationRow
              key={row.id}
              row={row}
              cancelling={cancellingId === row.id}
              disabled={cancellingId !== null}
              onCancel={onCancel}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

type RowProps = {
  row: MyReservation
  cancelling: boolean
  disabled: boolean
  onCancel: (id: number) => void
}

function ReservationRow({ row, cancelling, disabled, onCancel }: RowProps) {
  const { t } = useTranslation()
  const start = hhmm(row.start_time)
  const active = row.status === 'booked'
  // 取り消しの確かめ（「もう一度押すと取り消します」と「やめる」）が出ているとき（行の下の段に出す）
  const [armed, setArmed] = useState(false)

  return (
    <li className="space-y-2 border-t border-card-line p-3 first:border-t-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <DateChip date={row.visit_date} active={active} />
        <div className={`min-w-32 flex-1 space-y-0.5 ${active ? '' : 'text-ink-sub'}`}>
          <p className="font-bold tabular-nums">
            {/* 日付の札は読み上げないので、日付は、読み上げる文字として持つ */}
            <span className="sr-only">
              <Ruby
                text={t('visit.date', {
                  ...monthDay(row.visit_date),
                  weekday: stripRuby(t(`visit.weekday.${weekdayOf(row.visit_date)}`)),
                })}
              />{' '}
            </span>
            {t('visit.time_range', { start, end: endOf(start) })}
          </p>
          <p className="text-sm text-ink-sub">
            <Ruby text={t('visit.visitors', { count: row.party_size })} />
          </p>
          <StatusBadge tone={active ? 'success' : 'neutral'}>
            <Text k={`visit.status.${row.status}`} />
          </StatusBadge>
        </div>
        {active && row.can_cancel && (
          // 確かめの状態のときは、行の下の段に、幅いっぱいで出す（横に並べると、時刻や人数が細く潰れる。#407 ようこさん）
          <div className={armed ? 'w-full' : ''}>
            <ConfirmButton
              onArmedChange={setArmed}
              labelKey="visit.cancel"
              confirmKey="visit.cancel_confirm"
              busyKey="visit.cancelling"
              busy={cancelling}
              disabled={disabled}
              onConfirm={() => onCancel(row.id)}
              className="min-h-11 rounded-xl border border-field-line bg-page px-3 text-sm font-bold shadow-sm"
            />
          </div>
        )}
      </div>
      {row.cancel_reason && (
        <p className="text-sm">
          <Text k="visit.cancel_reason" />
          {/* 施設が入力した理由は、辞書を通さず文字としてだけ出す（FR-016） */}
          <span className="whitespace-pre-wrap">{row.cancel_reason}</span>
        </p>
      )}
      {active && !row.can_cancel && (
        <p className="text-sm text-orange-700">
          <Text k="visit.deadline_passed" />
        </p>
      )}
    </li>
  )
}
