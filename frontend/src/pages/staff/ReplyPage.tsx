import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { themeIconName } from '../../components/themeIcon'
import { Icon } from '../../components/Icon'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError, api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentName } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import { timeInJapan } from './contactBookTimeline'
import { currentRecord, DAY_SLOT, type StaffContactBook, type StaffRecord } from './recordValues'
import {
  MAX_NOTE_LENGTH,
  noteLength,
  replyBody,
  toggleTemplate,
  type WaitingRequest,
  type WaitingRequests,
} from './replyForm'
import { monthDay } from './residentRows'

type Send = { requestId: number; templateIds: number[]; note: string }

/**
 * 職員の返事の画面（UI-S03。spec 001 の T062・FR-030）。`/staff/residents/:residentId/requests`
 * 返事待ちのリクエストごとに、テーマ・送られた日・日数と、そのテーマの定型文のボタンを出す。
 * 定型文を 1 つ以上選んで「送る」（リクエストを開いてから 3 タップ以内。SC-007）。書き足しは 100 文字まで、任意。
 * 送ったら記録の画面に戻る（docs/画面設計.md「2」）。ほかの職員が先に返事をしていたら（409）、文言を出して読み直す。
 */
export function ReplyPage() {
  const { residentId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const requestsKey = ['staff', 'requests', residentId]

  const requests = useQuery({
    queryKey: requestsKey,
    queryFn: () => api.get<WaitingRequests>(`/api/staff/residents/${residentId}/requests`),
  })
  // 入居者の呼び名・居室（記録の画面で読んだものがあれば、それを使う）
  const book = useQuery({
    queryKey: ['staff', 'contact-book', residentId, 'today'],
    queryFn: () => api.get<StaffContactBook>(`/api/staff/residents/${residentId}/contact-book`),
  })
  const send = useMutation({
    mutationFn: ({ requestId, templateIds, note }: Send) =>
      api.post(`/api/staff/requests/${requestId}/reply`, replyBody(templateIds, note)),
    onSuccess: async () => {
      // 一覧の件数・連絡帳の見返しにも返事が入る
      await Promise.all(
        [requestsKey, ['staff', 'residents'], ['staff', 'contact-book', residentId]].map(
          (queryKey) => queryClient.invalidateQueries({ queryKey }),
        ),
      )
      void navigate(`/staff/residents/${residentId}`)
    },
    onError: (error) => {
      // ほかの職員が先に返事をした・家族が取り消した（409）なら、今の返事待ちを読み直す
      if (error instanceof ApiError && error.status === 409) {
        void queryClient.invalidateQueries({ queryKey: requestsKey })
      }
    },
  })

  if (requests.isPending) return <Message k="layout.loading" />
  if (requests.isError) return <Message k={messageKeyOf(requests.error)} />
  return (
    <ReplyView
      residentId={residentId}
      resident={book.data?.resident ?? null}
      records={book.data?.records ?? null}
      requests={requests.data.requests}
      sendingId={send.isPending ? send.variables.requestId : null}
      errorKey={send.isError ? messageKeyOf(send.error) : null}
      onSend={(value) => send.mutate(value)}
    />
  )
}

type ViewProps = {
  residentId: string
  resident: StaffContactBook['resident'] | null
  // 今日の記録（返事を書くときの手がかり。#457）。まだ読めていないときは null
  records?: StaffRecord[] | null
  requests: WaitingRequest[]
  sendingId: number | null
  errorKey: string | null
  onSend: (send: Send) => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function ReplyView({
  residentId,
  resident,
  records,
  requests,
  sendingId,
  errorKey,
  onSend,
}: ViewProps) {
  const { t } = useTranslation()
  return (
    <section className="space-y-4 p-4">
      <Link
        to={`/staff/residents/${residentId}`}
        className="-mb-2 inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-primary"
      >
        <Icon name="prev" />
        <Text k="reply_page.back" />
      </Link>
      {/* 見出しは、入居者の名前を大きく（枠や印は増やさず、文字の大きさで読ませる。#457） */}
      <div>
        {resident && (
          <>
            <p className="text-sm text-ink-sub">
              <Ruby text={t('reply_page.room', { room: resident.room })} />
            </p>
            <p className="text-2xl font-extrabold">
              <ResidentName name={resident.display_name} ruby={resident.display_name_ruby} />
            </p>
          </>
        )}
        <h1 className={resident ? 'mt-1 text-ink-sub' : 'text-2xl font-bold'}>
          <Ruby text={t('reply_page.title_count', { count: requests.length })} />
        </h1>
      </div>

      {errorKey && (
        <p role="alert" className="rounded-2xl bg-card p-4 font-bold text-red-700 shadow-sm">
          <Text k={errorKey} />
        </p>
      )}

      {requests.length === 0 ? (
        <Message k="reply_page.none" />
      ) : (
        requests.map((request) => (
          <RequestCard
            key={request.id}
            request={request}
            records={records ?? null}
            sending={sendingId === request.id}
            disabled={sendingId !== null}
            onSend={onSend}
          />
        ))
      )}
    </section>
  )
}

type CardProps = {
  request: WaitingRequest
  records: StaffRecord[] | null
  sending: boolean
  disabled: boolean
  onSend: (send: Send) => void
}

// 今日の記録の 1 行に出す欄（食事の朝・昼・夜と、機嫌・眠り。おやつは出さない）
const TODAY_SLOTS = [
  { item: 'meal', slot: 'breakfast', labelKey: 'record.slot.breakfast' },
  { item: 'meal', slot: 'lunch', labelKey: 'record.slot.lunch' },
  { item: 'meal', slot: 'dinner', labelKey: 'record.slot.dinner' },
  { item: 'mood', slot: DAY_SLOT, labelKey: 'record.item.mood' },
  { item: 'sleep', slot: DAY_SLOT, labelKey: 'record.item.sleep' },
] as const

/**
 * リクエスト 1 つ：家族の問いを見出しに、その下に今日の記録（手がかり）、定型文の行、書き足し、送る。
 * 定型文は、押すと ✓ が付く行（`aria-pressed`。色に加えて ✓ と太字で示す）。
 */
function RequestCard({ request, records, sending, disabled, onSend }: CardProps) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<number[]>([])
  const [note, setNote] = useState('')
  const tooLong = noteLength(note) > MAX_NOTE_LENGTH
  const received = new Date(request.created_at)

  return (
    <form
      className="rounded-[18px] bg-card px-5 pt-5 pb-6 shadow-[0_1px_2px_rgb(15_31_61/0.04),0_6px_16px_rgb(15_31_61/0.05)]"
      onSubmit={(event) => {
        event.preventDefault()
        onSend({ requestId: request.id, templateIds: selected, note })
      }}
    >
      <p className="text-sm text-ink-sub">
        <Text k="reply_page.from" />
        <span className="ml-3">
          <Ruby
            text={t('reply_page.received', {
              ...monthDay(dateInJapan(received)),
              time: timeInJapan(request.created_at),
            })}
          />
        </span>
        {/* 1 日以上たっているときは、注意の色の文字で（印は増やさない） */}
        <span className={`ml-3 ${request.days > 0 ? 'font-bold text-amber-800' : ''}`}>
          <Ruby
            text={
              request.days === 0
                ? t('reply_page.days_today')
                : t('reply_page.waiting_days', { count: request.days })
            }
          />
        </span>
      </p>
      <h2 className="mt-1.5 text-xl leading-normal font-bold">
        <Icon
          name={themeIconName(request.theme_code)}
          className="mr-2 text-[0.85em] text-primary"
        />
        <Ruby text={t('reply_page.question', { theme: t(request.theme_code) })} />
      </h2>

      {records && (
        <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 rounded-xl bg-page px-3.5 py-2.5 text-sm text-ink-sub">
          <span>
            <Text k="reply_page.today_records" />
          </span>
          {TODAY_SLOTS.map((slot) => {
            const record = currentRecord(records, slot.item, slot.slot)
            return (
              <span key={slot.labelKey}>
                <Text k={slot.labelKey} />
                <span className={`ml-1 ${record ? 'font-bold text-ink' : ''}`}>
                  <Text
                    k={record ? `record.value.${slot.item}.${record.value}` : 'reply_page.not_yet'}
                  />
                </span>
              </span>
            )
          })}
        </p>
      )}

      <fieldset className="mt-5">
        <legend className="mb-1.5 text-sm font-bold text-ink-sub">
          <Text k="reply_page.choose" />
        </legend>
        <ul className="border-t border-card-line">
          {request.templates.map((template) => {
            const on = selected.includes(template.id)
            return (
              <li key={template.id} className="border-b border-card-line">
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => setSelected((current) => toggleTemplate(current, template.id))}
                  className={`flex min-h-14 w-full items-center gap-3.5 py-2.5 text-left text-[17px] leading-normal ${
                    on ? 'font-bold text-primary-dark' : ''
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`flex size-6 shrink-0 items-center justify-center rounded-full text-xs ${
                      on ? 'bg-primary text-white' : 'ring-2 ring-[#b7c0cd] ring-inset'
                    }`}
                  >
                    {on && <Icon name="check" />}
                  </span>
                  <span>
                    <Text k={template.code} />
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </fieldset>

      <label className="mt-5 block text-sm font-bold text-ink-sub">
        <Text k="reply_page.note" />
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          aria-invalid={tooLong}
          className="mt-1.5 block w-full rounded-xl border border-field-line bg-card p-3 text-base font-normal text-ink aria-[invalid=true]:border-2 aria-[invalid=true]:border-red-700"
        />
        <span
          className={`mt-1 block text-right font-normal ${tooLong ? 'font-bold text-red-700' : 'text-ink-sub'}`}
        >
          {t('reply_page.note_count', { count: noteLength(note) })}
        </span>
      </label>

      <button
        type="submit"
        disabled={selected.length === 0 || tooLong || disabled}
        className="mt-3 flex min-h-13 w-full items-center justify-center gap-2 rounded-[14px] bg-primary p-3 text-[17px] font-bold text-white disabled:opacity-50"
      >
        <Icon name="send" />
        <span>
          <Text k={sending ? 'reply_page.sending' : 'reply_page.send_reply'} />
        </span>
      </button>
    </form>
  )
}

/** 日本時間の日付（"YYYY-MM-DD"）。 */
function dateInJapan(at: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo' }).format(at)
}
