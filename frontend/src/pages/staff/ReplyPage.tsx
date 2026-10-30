import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError, api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { timeInJapan } from './contactBookTimeline'
import type { StaffContactBook } from './recordValues'
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
  requests: WaitingRequest[]
  sendingId: number | null
  errorKey: string | null
  onSend: (send: Send) => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function ReplyView({
  residentId,
  resident,
  requests,
  sendingId,
  errorKey,
  onSend,
}: ViewProps) {
  return (
    <section className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        <Text k="reply_page.title" />
        {resident && (
          <span className="ml-3 text-base font-normal">
            <span className="mr-2 text-gray-600">{resident.room}</span>
            {/* 入居者の呼び名は、辞書を通さずそのまま出す */}
            {resident.display_name}
          </span>
        )}
      </h1>

      {errorKey && (
        <p role="alert" className="rounded border border-red-700 p-3 text-red-700">
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
            sending={sendingId === request.id}
            disabled={sendingId !== null}
            onSend={onSend}
          />
        ))
      )}

      <Link to={`/staff/residents/${residentId}`} className="inline-block text-primary underline">
        <Text k="reply_page.back" />
      </Link>
    </section>
  )
}

type CardProps = {
  request: WaitingRequest
  sending: boolean
  disabled: boolean
  onSend: (send: Send) => void
}

function RequestCard({ request, sending, disabled, onSend }: CardProps) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<number[]>([])
  const [note, setNote] = useState('')
  const tooLong = noteLength(note) > MAX_NOTE_LENGTH
  const received = new Date(request.created_at)

  return (
    <form
      className="space-y-3 rounded border-2 border-field-line p-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSend({ requestId: request.id, templateIds: selected, note })
      }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-bold">
          <span aria-hidden="true">{request.theme_emoji} </span>
          <Text k={request.theme_code} />
        </h2>
        <span className="text-sm text-gray-600">
          <Ruby
            text={t('reply_page.received', {
              ...monthDay(dateInJapan(received)),
              time: timeInJapan(request.created_at),
            })}
          />
          <span className="ml-2" />
          <Ruby
            text={
              request.days === 0
                ? t('reply_page.days_today')
                : t('reply_page.days', { count: request.days })
            }
          />
        </span>
      </div>

      <fieldset>
        <legend className="mb-2 text-sm">
          <Text k="reply_page.choose" />
        </legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {request.templates.map((template) => {
            const on = selected.includes(template.id)
            return (
              <button
                key={template.id}
                type="button"
                aria-pressed={on}
                onClick={() => setSelected((current) => toggleTemplate(current, template.id))}
                className={`min-h-12 rounded border-2 p-2 text-left ${
                  on ? 'border-primary bg-primary text-white' : 'border-field-line bg-white'
                }`}
              >
                <Text k={template.code} />
              </button>
            )
          })}
        </div>
      </fieldset>

      <label className="block text-sm">
        <Text k="reply_page.note" />
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          aria-invalid={tooLong}
          className="mt-1 block w-full rounded border-2 border-field-line p-2 aria-[invalid=true]:border-red-700"
        />
        <span
          className={`block text-right ${tooLong ? 'font-bold text-red-700' : 'text-gray-600'}`}
        >
          {t('reply_page.note_count', { count: noteLength(note) })}
        </span>
      </label>

      <button
        type="submit"
        disabled={selected.length === 0 || tooLong || disabled}
        className="w-full rounded bg-primary p-3 text-lg font-bold text-white disabled:opacity-50"
      >
        <Text k={sending ? 'reply_page.sending' : 'reply_page.send'} />
      </button>
    </form>
  )
}

/** 日本時間の日付（"YYYY-MM-DD"）。 */
function dateInJapan(at: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo' }).format(at)
}
