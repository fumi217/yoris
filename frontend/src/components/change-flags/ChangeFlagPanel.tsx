import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { Ruby } from '../../i18n/Ruby'
import { Message } from '../Message'
import { Text } from '../Text'
import {
  confirmBody,
  confirmFailure,
  hasUnconfirmed,
  isShown,
  itemOf,
  jstDate,
  monthDay,
  noteLength,
  NOTE_MAX,
  sortedEvidence,
  type ChangeFlag,
  type ChangeFlags,
} from './changeFlags'

/**
 * 入居者を開いた画面に置く、目印の欄（spec 006 の 006-T013・T018。FR-003・FR-004・FR-008〜FR-010）。
 * 今の目印（当てはまった決まりともとの記録）、「確かめた」とひとこと、過去の目印を出す。
 * 事務員は職員の画面を開けないので、この欄も出ない（API も 403。FR-006）。
 * 通知・音・画面を遮る表示は出さない（FR-005）。
 */
export function ChangeFlagPanel({ residentId }: { residentId: number }) {
  const queryClient = useQueryClient()
  const key = ['staff', 'change-flags', residentId]
  const flags = useQuery({
    queryKey: key,
    queryFn: () => api.get<ChangeFlags>(`/api/staff/residents/${residentId}/change-flags`),
  })

  // 確かめると、入居者一覧の「確かめていない目印：◯件」も変わる
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: key }),
      queryClient.invalidateQueries({ queryKey: ['staff', 'residents'] }),
    ])
  const confirm = useMutation({
    mutationFn: (note: string) =>
      api.post(`/api/staff/residents/${residentId}/change-flags/confirm`, confirmBody(note)),
    onSuccess: () => refresh(),
    onError: (error) => {
      // ほかの職員が先に確かめた：読み直して、確かめ済みの様子を見せる
      if (confirmFailure(error).conflict) void refresh()
    },
  })
  // 案内は、直前に押した結果だけから決める（押し直せば、前の案内は消える）
  const failure = confirmFailure(confirm.error)

  if (flags.isError) return <Message k={messageKeyOf(flags.error)} />
  if (!flags.data) return null
  return (
    <ChangeFlagPanelView
      data={flags.data}
      saving={confirm.isPending}
      conflict={failure.conflict}
      errorKey={failure.errorKey}
      onConfirm={(note) => confirm.mutate(note)}
    />
  )
}

type ViewProps = {
  data: ChangeFlags
  saving: boolean
  // ほかの職員が先に確かめた（409 already_confirmed）
  conflict: boolean
  errorKey: string | null
  onConfirm: (note: string) => void
}

export function ChangeFlagPanelView({ data, saving, conflict, errorKey, onConfirm }: ViewProps) {
  // 出せない目印（知らない決まりなど）は数えない。見えない目印を「確かめた」ことにしないため
  const current = data.current.filter(isShown)
  const history = data.history.filter(isShown)
  // 今も過去も目印がなければ、欄ごと出さない（記録の画面を散らかさない）
  if (current.length === 0 && history.length === 0) return null

  return (
    <section
      aria-labelledby="change-flags-title"
      className="space-y-3 rounded border-2 border-amber-700 bg-amber-50 p-3"
    >
      {current.length > 0 && (
        <>
          <h2 id="change-flags-title" className="text-lg font-bold">
            <Text k="change.title" />
          </h2>
          <ul className="space-y-3">
            {current.map((flag) => (
              <FlagItem key={flag.id} flag={flag} showStatus />
            ))}
          </ul>
          <p className="text-sm">
            <Text k="change.guide" />
          </p>
          {hasUnconfirmed(current) && (
            <ConfirmForm saving={saving} errorKey={errorKey} onConfirm={onConfirm} />
          )}
          {/* 案内の意味は「全部、確かめ済みになった」。未確認の目印がまた出ているときは、出さない */}
          {conflict && !hasUnconfirmed(current) && (
            <p role="status" className="text-sm font-bold">
              <Text k="change.already_confirmed" />
            </p>
          )}
        </>
      )}
      {history.length > 0 && (
        <div>
          <h3 id={current.length === 0 ? 'change-flags-title' : undefined} className="font-bold">
            <Text k="change.history_title" />
          </h3>
          <ul className="mt-2 space-y-3">
            {history.map((flag) => (
              <FlagItem key={flag.id} flag={flag} showStatus={false} />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

/** 目印 1 件：当てはまった決まりの文、もとの記録、確かめた記録。 */
function FlagItem({ flag, showStatus }: { flag: ChangeFlag; showStatus: boolean }) {
  const { t } = useTranslation()
  const item = itemOf(flag.rule_code)
  const evidence = sortedEvidence(flag.evidence)
  if (!item || evidence.length === 0) return null

  const dateOf = (date: string) => {
    const { month, day } = monthDay(date)
    return t('record_page.date', { month, day })
  }
  const first = evidence[0]
  const from =
    item === 'meal'
      ? t('change.from_meal', {
          date: dateOf(first.date),
          slot: t(`record_page.slot.${first.slot}`),
        })
      : dateOf(first.date)
  const unconfirmed = flag.status === 'unconfirmed'

  return (
    <li
      className={`rounded border-2 p-3 ${
        unconfirmed || !showStatus ? 'border-amber-700 bg-white' : 'border-gray-400 bg-gray-100'
      }`}
    >
      <p className="font-bold">
        <Ruby text={t(`change.rule.${flag.rule_code}`, { from, count: flag.streak })} />
      </p>
      {showStatus && (
        <p className="text-sm font-bold">
          <Text k={`change.status.${flag.status}`} />
        </p>
      )}
      {!showStatus && (
        <p className="text-sm">
          <Ruby text={t('change.started', { date: dateOf(jstDate(flag.started_at)) })} />
          {flag.cleared_at && (
            <>
              {' '}
              <Ruby text={t('change.cleared', { date: dateOf(jstDate(flag.cleared_at)) })} />
            </>
          )}
        </p>
      )}
      <p className="mt-1 text-sm font-bold">
        <Text k="change.evidence_title" />
      </p>
      <ul className="list-disc pl-5 text-sm">
        {evidence.map((record) => (
          <li key={record.record_id}>
            <Ruby
              text={t(item === 'meal' ? 'change.evidence_slot' : 'change.evidence', {
                date: dateOf(record.date),
                item: t(`record.item.${item}`),
                // 区分があるのは食事だけ（機嫌・眠りは 1 日に 1 つ）
                slot: item === 'meal' ? t(`record.slot.${record.slot}`) : '',
                value: t(`record.value.${item}.${record.value}`),
              })}
            />
          </li>
        ))}
      </ul>
      {flag.confirmations.map((confirmation) => (
        <div
          key={`${confirmation.confirmed_at}-${confirmation.staff_display_name}`}
          className="mt-2 text-sm"
        >
          {/* 職員の名前とひとことは、辞書の文に埋め込まず、文字のまま出す（FR-013） */}
          <p>
            <Text k="change.confirmed_by" />
            {confirmation.staff_display_name}（
            <Ruby text={dateOf(jstDate(confirmation.confirmed_at))} />）
          </p>
          {confirmation.note && (
            <p>
              <Text k="change.note" />
              {confirmation.note}
            </p>
          )}
        </div>
      ))}
    </li>
  )
}

/** 「確かめた」とひとこと（100 文字まで・任意）。入居者ごとに 1 回で、今の目印をまとめて確かめる。 */
function ConfirmForm({
  saving,
  errorKey,
  onConfirm,
}: {
  saving: boolean
  errorKey: string | null
  onConfirm: (note: string) => void
}) {
  const { t } = useTranslation()
  const [note, setNote] = useState('')
  const tooLong = noteLength(note) > NOTE_MAX

  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        onConfirm(note)
      }}
    >
      <label className="block text-sm">
        <Text k="change.note_label" />
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          aria-invalid={tooLong}
          aria-describedby="change-note-count"
          className="mt-1 block w-full rounded border-2 border-gray-500 bg-white p-2 aria-[invalid=true]:border-red-700"
        />
        <span
          id="change-note-count"
          className={`block text-right ${tooLong ? 'font-bold text-red-700' : 'text-gray-700'}`}
        >
          {t('change.note_count', { count: noteLength(note) })}
        </span>
      </label>
      {errorKey && (
        <p role="alert" className="text-sm text-red-700">
          <Text k={errorKey} />
        </p>
      )}
      <button
        type="submit"
        disabled={tooLong || saving}
        className="min-h-11 rounded bg-sky-700 px-4 py-2 font-bold text-white disabled:opacity-60"
      >
        <Text k={saving ? 'change.confirming' : 'change.confirm'} />
      </button>
    </form>
  )
}
