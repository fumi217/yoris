import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { ConfirmButton } from '../../components/ConfirmButton'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import {
  APPROVALS_KEY,
  REASON_MAX,
  isValidReason,
  jstDate,
  reasonLength,
  sortedWarnings,
  waitingHours,
  type Approval,
  type ApprovalAction,
  type ApprovalTab,
} from './memoApprovalsView'
import { monthDay } from './residentRows'

/**
 * 様子のメモの承認（UI-S07。spec 007 の 007-T023。FR-011〜FR-016。リーダー・施設長）。
 * 承認待ち：原文・整えた日本語・訳し戻し・注意の印を並べて見て、承認する・理由を書いて戻す。
 * 承認済み：間違いに気づいたときに、理由を書いて公開を取り下げる。
 * 通知・音・画面を遮る表示は出さない（FR-015）。
 */
export function MemoApprovals() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<ApprovalTab>('pending')
  const list = useQuery({
    queryKey: [...APPROVALS_KEY, 'list', tab],
    queryFn: () => api.get<Approval[]>(`/api/staff/memo-approvals?status=${tab}`),
  })
  const act = useMutation({
    mutationFn: ({ id, action, reason }: { id: number; action: ApprovalAction; reason?: string }) =>
      api.post(
        `/api/staff/memo-approvals/${id}/${action}`,
        reason === undefined ? undefined : { reason },
      ),
    // 成功のときも、ほかの人が先に動かした（409）ときも、読み直して今の状態を見せる
    onSettled: () => queryClient.invalidateQueries({ queryKey: APPROVALS_KEY }),
  })

  // 読み込み中・エラーは、一覧の場所だけで出す（見出しとタブのボタンは、いつも出しておく。2.4.3）
  return (
    <MemoApprovalsView
      tab={tab}
      onTab={(next) => {
        // 通信中に reset すると「処理中」の印まで消え、同じメモのボタンがまた押せてしまう。
        // 通信が終わるまでは、前の結果の案内を残したまま切り替える（終わった結果が、そのまま出る）
        if (!act.isPending) act.reset()
        setTab(next)
      }}
      items={list.data ?? null}
      listErrorKey={list.isError ? messageKeyOf(list.error) : null}
      busyId={act.isPending ? act.variables.id : null}
      errorKey={act.isError ? messageKeyOf(act.error) : null}
      errorId={act.isError ? act.variables.id : null}
      doneAction={act.isSuccess ? act.variables.action : null}
      onAct={(id, action, reason) => act.mutate({ id, action, reason })}
    />
  )
}

type ViewProps = {
  tab: ApprovalTab
  onTab: (tab: ApprovalTab) => void
  // null は、まだ読み込み中（前のタブの一覧は残さない。別の状態のメモに、合わないボタンが付かないように）
  items: Approval[] | null
  // 一覧を読み込めなかったときのエラーの文言のキー
  listErrorKey: string | null
  // いま承認・戻す・取り下げている最中のメモ（そのメモのボタンだけ押せなくする）
  busyId: number | null
  // 操作ができなかったときの理由と、押したメモ。押したメモの近くに出す（一覧が長いと、
  // 画面の上の文は、押した場所から遠く、画面の外になるため）
  errorKey: string | null
  errorId: number | null
  // 直前に済ませた操作（読み上げにも伝える。4.1.3）
  doneAction: ApprovalAction | null
  onAct: (id: number, action: ApprovalAction, reason?: string) => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function MemoApprovalsView({
  tab,
  onTab,
  items,
  listErrorKey,
  busyId,
  errorKey,
  errorId,
  doneAction,
  onAct,
}: ViewProps) {
  const { t } = useTranslation()
  // 押したメモが今の一覧にあれば、そのメモの中に出す。ないとき（ほかのリーダーが先に承認して、
  // 読み直しで一覧から消えた 409 など）は、見えなくならないよう、画面の上に出す
  const errorInList = items?.some((item) => item.id === errorId) ?? false
  const topError = errorKey !== null && !errorInList
  // 画面の上に出す文は、下までスクロールしていると見えない。出たときに、見える位置へ動かす
  const topErrorRef = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    if (topError) topErrorRef.current?.scrollIntoView({ block: 'center' })
  }, [topError, errorKey, errorId])
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        <Text k="memo_approval.title" />
      </h1>
      <p className="rounded border-2 border-red-700 bg-red-50 p-2 font-bold">
        <Text k="memo.call_if_urgent" />
      </p>

      <div role="group" aria-label={stripRuby(t('memo_approval.state'))} className="flex gap-2">
        {(['pending', 'approved'] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={tab === value}
            onClick={() => onTab(value)}
            className={`min-h-11 rounded border-2 px-4 py-2 ${
              tab === value
                ? 'border-sky-700 bg-sky-700 font-bold text-white'
                : 'border-gray-500 bg-white'
            }`}
          >
            <Text k={`memo_approval.tab_${value}`} />
          </button>
        ))}
      </div>
      {tab === 'approved' && (
        <p className="text-sm text-gray-700">
          <Text k="memo_approval.approved_note" />
        </p>
      )}

      <p role="status" aria-live="polite" className="min-h-6 text-sm font-bold">
        {doneAction && <Text k={`memo_approval.done_${doneAction}`} />}
      </p>
      {topError && errorKey && (
        <p ref={topErrorRef} role="alert" className="text-sm text-red-700">
          <Text k={errorKey} />
        </p>
      )}

      {listErrorKey ? (
        <Message k={listErrorKey} />
      ) : items === null ? (
        <Message k="layout.loading" />
      ) : items.length === 0 ? (
        <p>
          <Text k={`memo_approval.empty_${tab}`} />
        </p>
      ) : (
        <ul className="space-y-4">
          {items.map((item) => (
            <li key={item.id}>
              <MemoCard
                item={item}
                tab={tab}
                busy={busyId === item.id}
                errorKey={errorId === item.id ? errorKey : null}
                onAct={onAct}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function MemoCard({
  item,
  tab,
  busy,
  errorKey,
  onAct,
}: {
  item: Approval
  tab: ApprovalTab
  busy: boolean
  errorKey: string | null
  onAct: ViewProps['onAct']
}) {
  const { t } = useTranslation()
  // 戻す理由・取り下げる理由を書いているところ
  const [mode, setMode] = useState<'return' | 'unpublish' | null>(null)
  const dateText = (date: string) => {
    const { month, day } = monthDay(date)
    return t('record_page.date', { month, day })
  }
  const warnings = sortedWarnings(item.warnings)
  const hours = item.waiting_minutes === null ? null : waitingHours(item.waiting_minutes)

  return (
    <article
      aria-labelledby={`memo-${item.id}`}
      className="space-y-3 rounded border-2 border-gray-500 bg-white p-3"
    >
      <header className="space-y-1">
        {/* 入居者の呼び名・職員の名前・メモの文は、辞書を通さず、文字のまま出す（FR-017） */}
        <h2 id={`memo-${item.id}`} className="text-lg font-bold">
          {item.resident_name}
        </h2>
        <p className="text-sm">
          <Text k="memo_approval.author" />
          {item.author_name}
          <span className="ml-3">
            <Ruby text={t('memo_approval.written_on', { date: dateText(item.memo_date) })} />
          </span>
        </p>
        {hours !== null && (
          <p className={item.overdue ? 'font-bold text-amber-900' : 'text-sm'}>
            {item.overdue && <span aria-hidden="true">⚠️ </span>}
            <Ruby
              text={
                hours === 0
                  ? t('memo_approval.waiting_under_hour')
                  : t('memo_approval.waiting_hours', { count: hours })
              }
            />
            {item.overdue && (
              <span className="ml-3">
                <Text k="memo.waiting_over_day" />
              </span>
            )}
          </p>
        )}
        {tab === 'approved' && item.approved_at && (
          <p className="text-sm">
            <Ruby
              text={t('memo_approval.approved_on', { date: dateText(jstDate(item.approved_at)) })}
            />
          </p>
        )}
      </header>

      {warnings.length > 0 && (
        <div className="rounded border-2 border-amber-700 bg-amber-50 p-2">
          <h3 className="font-bold">
            <span aria-hidden="true">⚠️ </span>
            <Text k="memo_approval.warnings_title" />
          </h3>
          <ul className="list-disc pl-5 text-sm">
            {warnings.map((code) => (
              <li key={code}>
                <Text k={`memo_approval.warning.${code}`} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <section>
        <h3 className="font-bold">
          <Text k="memo.original" />（<Text k={`memo.lang.${item.source_lang}`} />）
        </h3>
        <p className="whitespace-pre-wrap break-words">{item.original_text}</p>
      </section>
      <section>
        <h3 className="font-bold">
          <Text k="memo.rewritten" />
        </h3>
        <p className="whitespace-pre-wrap break-words">
          {item.rewritten_text ?? <Text k="memo_approval.no_rewritten" />}
        </p>
      </section>
      <section>
        <h3 className="font-bold">
          <Text k="memo.back_translation" />
        </h3>
        <p className="whitespace-pre-wrap break-words">
          {item.back_translation ?? <Text k="memo_approval.no_back_translation" />}
        </p>
      </section>

      {tab === 'pending' && (
        <>
          <ul className="list-disc pl-5 text-sm">
            <li>
              <Text k="memo.check_other_names" />
            </li>
            <li>
              <Text k="memo.check_medical" />
            </li>
          </ul>
          {item.is_own ? (
            // 本人のメモは承認も戻すもできない。ほかのリーダー・施設長を待つ（FR-011a）
            <p className="text-sm font-bold">
              <Text k="memo.waiting_other_leader" />
            </p>
          ) : mode === null ? (
            <div className="flex flex-wrap gap-3">
              {/* 承認すると家族に見える。押し間違えないよう、2 回押して決める */}
              <ConfirmButton
                labelKey="memo_approval.approve"
                confirmKey="memo_approval.approve_confirm"
                busyKey="memo_approval.approving"
                busy={busy}
                describedBy={`memo-${item.id}`}
                onConfirm={() => onAct(item.id, 'approve')}
                className="min-h-11 rounded bg-sky-700 px-4 py-2 font-bold text-white"
              />
              <button
                type="button"
                disabled={busy}
                aria-describedby={`memo-${item.id}`}
                onClick={() => setMode('return')}
                className="min-h-11 rounded border-2 border-gray-500 bg-white px-4 py-2 disabled:opacity-60"
              >
                <Text k="memo_approval.return" />
              </button>
            </div>
          ) : (
            <ReasonForm
              id={`reason-${item.id}`}
              labelKey="memo_approval.return_label"
              submitKey="memo_approval.return_submit"
              busyKey="memo_approval.returning"
              busy={busy}
              onSubmit={(reason) => onAct(item.id, 'return', reason)}
              onCancel={() => setMode(null)}
            />
          )}
        </>
      )}

      {tab === 'approved' &&
        (mode === null ? (
          <button
            type="button"
            disabled={busy}
            aria-describedby={`memo-${item.id}`}
            onClick={() => setMode('unpublish')}
            className="min-h-11 rounded border-2 border-gray-500 bg-white px-4 py-2 disabled:opacity-60"
          >
            <Text k="memo_approval.unpublish" />
          </button>
        ) : (
          <ReasonForm
            id={`reason-${item.id}`}
            labelKey="memo_approval.unpublish_label"
            submitKey="memo_approval.unpublish_submit"
            busyKey="memo_approval.unpublishing"
            busy={busy}
            onSubmit={(reason) => onAct(item.id, 'unpublish', reason)}
            onCancel={() => setMode(null)}
          />
        ))}

      {errorKey && (
        <p role="alert" className="text-sm text-red-700">
          <Text k={errorKey} />
        </p>
      )}
    </article>
  )
}

type ReasonFormProps = {
  id: string
  labelKey: string
  submitKey: string
  busyKey: string
  busy: boolean
  onSubmit: (reason: string) => void
  onCancel: () => void
}

/** 戻す・公開を取り下げるときの理由（1〜200 文字・必須。FR-013・FR-013a）。 */
export function ReasonForm({
  id,
  labelKey,
  submitKey,
  busyKey,
  busy,
  onSubmit,
  onCancel,
}: ReasonFormProps) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const length = reasonLength(reason)
  const tooLong = length > REASON_MAX

  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit(reason.trim())
      }}
    >
      <label className="block text-sm">
        <Text k={labelKey} />
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={2}
          aria-invalid={tooLong}
          aria-describedby={`${id}-count`}
          className="mt-1 block w-full rounded border-2 border-gray-500 bg-white p-2 aria-[invalid=true]:border-red-700"
        />
        <span
          id={`${id}-count`}
          className={`block text-right ${tooLong ? 'font-bold text-red-700' : 'text-gray-700'}`}
        >
          {t('memo_approval.reason_count', { count: length })}
        </span>
      </label>
      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          disabled={!isValidReason(reason) || busy}
          className="min-h-11 rounded bg-sky-700 px-4 py-2 font-bold text-white disabled:opacity-60"
        >
          <Text k={busy ? busyKey : submitKey} />
        </button>
        <button type="button" onClick={onCancel} className="min-h-11 text-sky-700 underline">
          <Text k="layout.confirm_stop" />
        </button>
      </div>
    </form>
  )
}
