import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { OccupationLabel } from '../../components/OccupationLabel'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import {
  aiNoticeKey,
  showsCallIfUrgent,
  chronological,
  marksNoticeRead,
  nextBefore,
  PAGE_SIZE,
  sourceParts,
  type InquiryMessage,
  type InquirySource,
  type SendResult,
} from './inquiryView'
import { markSentOnce } from './contactBookView'
import { useOnVisible } from './useOnVisible'

const MESSAGES_KEY = ['family-inquiry-messages'] as const
const NOTIFICATIONS_KEY = ['family', 'notifications'] as const
// 1 回に送れる文字数（FR-001。API も 500 文字を超えると 422）
const BODY_MAX = 500

/**
 * 家族の「お問い合わせ」（AI に質問する）画面（UI-F05。spec 004 の 004-T020）。
 * 画面に戻ったときの読み直し（職員の返事を出すため。research.md R-16）は、
 * TanStack Query の初期設定（refetchOnWindowFocus）で行う。
 */
export function Inquiry() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')
  const [errorKey, setErrorKey] = useState<string | null>(null)

  const messages = useInfiniteQuery({
    queryKey: MESSAGES_KEY,
    queryFn: ({ pageParam }) =>
      api.get<InquiryMessage[]>(
        `/api/family/inquiry/messages?limit=${PAGE_SIZE}${pageParam ? `&before=${pageParam}` : ''}`,
      ),
    initialPageParam: 0,
    getNextPageParam: nextBefore,
  })

  const send = useMutation({
    mutationFn: (body: string) => api.post<SendResult>('/api/family/inquiry/messages', { body }),
    onSuccess: () => {
      setDraft('')
      setErrorKey(null)
    },
    // AI が止まったときなどは、書いた文を消さずに残す（送り直せる。FR-026）
    onError: (error) => setErrorKey(messageKeyOf(error)),
    onSettled: () => queryClient.invalidateQueries({ queryKey: MESSAGES_KEY }),
  })

  // 職員の返事の発言が画面に出たら、その発言のお知らせを読んだことにする（Issue #244。
  // 連絡帳の返事と同じ決まり。発言ごとに 1 回だけ送る）
  const sent = useRef(new Set<number>())
  const { mutate: markRead } = useMutation({
    mutationFn: (messageId: number) => api.post(`/api/family/inquiry/messages/${messageId}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
    // 送れなかった発言は、次に画面に出たときに、また送れるようにする
    onError: (_error, messageId) => {
      sent.current.delete(messageId)
    },
  })
  const onStaffReplySeen = useCallback(
    (messageId: number) => {
      if (markSentOnce(sent.current, messageId)) markRead(messageId)
    },
    [markRead],
  )

  if (messages.isPending) return <Message k="layout.loading" />
  if (messages.isError) return <Message k={messageKeyOf(messages.error)} />

  return (
    <InquiryView
      messages={chronological(messages.data.pages)}
      hasOlder={messages.hasNextPage}
      onLoadOlder={() => messages.fetchNextPage()}
      draft={draft}
      onDraftChange={setDraft}
      sending={send.isPending ? send.variables : null}
      errorKey={errorKey}
      onSend={() => send.mutate(draft.trim())}
      onStaffReplySeen={onStaffReplySeen}
    />
  )
}

type ViewProps = {
  messages: InquiryMessage[]
  hasOlder: boolean
  onLoadOlder: () => void
  draft: string
  onDraftChange: (value: string) => void
  // 送っている途中の質問（答えが決まるまで、最後に出しておく）
  sending: string | null
  errorKey: string | null
  onSend: () => void
  // 職員の返事の発言が画面に出たときに呼ばれる（省略できる。テストでは渡さない）
  onStaffReplySeen?: (messageId: number) => void
}

/** 画面の見た目（API を呼ばない。テストではこれを描く）。 */
export function InquiryView({
  messages,
  hasOlder,
  onLoadOlder,
  draft,
  onDraftChange,
  sending,
  errorKey,
  onSend,
  onStaffReplySeen,
}: ViewProps) {
  // 文字の数え方を backend（500 文字まで）とそろえる（絵文字なども 1 文字と数える。PR #213 さとこ）
  const tooLong = Array.from(draft).length > BODY_MAX
  const canSend = sending === null && draft.trim() !== '' && !tooLong
  // 発言が増えた・送り始めたときは、いちばん新しい発言が見えるところまで送る（PR #213 さとこ）
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, sending])

  return (
    <div className="flex flex-col gap-3 p-4">
      <h2 className="font-bold">
        <Text k="inquiry.title" />
      </h2>
      {/* AI がお答えできないときは職員に伝えることを、常に出す（FR-012a） */}
      <p className="rounded bg-amber-50 p-2 text-sm">
        <Text k="inquiry.handoff_notice" />
      </p>

      {hasOlder && (
        <button type="button" onClick={onLoadOlder} className="text-sm text-sky-700 underline">
          <Text k="inquiry.load_older" />
        </button>
      )}

      <ol aria-live="polite" className="flex flex-col gap-3">
        {messages.length === 0 && sending === null && (
          <li className="text-gray-600">
            <Text k="inquiry.empty" />
          </li>
        )}
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} onStaffReplySeen={onStaffReplySeen} />
        ))}
        {sending !== null && (
          <>
            <FamilyBubble body={sending} />
            <li className="text-sm text-gray-600">
              <Text k="inquiry.thinking" />
            </li>
          </>
        )}
      </ol>
      <div ref={endRef} />

      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (canSend) onSend()
        }}
        className="flex flex-col gap-2"
      >
        <label htmlFor="inquiry-body" className="text-sm font-bold">
          <Text k="inquiry.input_label" />
        </label>
        <textarea
          id="inquiry-body"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          rows={3}
          className="rounded border p-2"
        />
        {tooLong && (
          <p className="text-sm text-red-700">
            <Text k="inquiry.too_long" />
          </p>
        )}
        <button
          type="submit"
          disabled={!canSend}
          className="rounded bg-sky-700 p-3 font-bold text-white disabled:opacity-60"
        >
          <Text k="inquiry.send" />
        </button>
        {errorKey && (
          <p role="alert" className="text-red-700">
            <Text k={errorKey} />
          </p>
        )}
      </form>
    </div>
  )
}

function MessageItem({
  message,
  onStaffReplySeen,
}: {
  message: InquiryMessage
  onStaffReplySeen?: (messageId: number) => void
}) {
  if (message.sender === 'family') return <FamilyBubble body={message.body} />
  if (message.sender === 'staff') return <StaffBubble message={message} onSeen={onStaffReplySeen} />
  return <AiBubble message={message} />
}

function FamilyBubble({ body }: { body: string }) {
  return (
    <li className="ml-8 rounded bg-sky-50 p-3">
      <p className="text-xs text-gray-600">
        <Text k="inquiry.sender_family" />
      </p>
      {/* 家族が書いた文は、辞書を通さず文字としてだけ出す（FR-028） */}
      <p className="whitespace-pre-wrap">{body}</p>
    </li>
  )
}

function AiBubble({ message }: { message: InquiryMessage }) {
  const noticeKey = aiNoticeKey(message)
  return (
    <li className="mr-8 rounded border p-3">
      <p className="text-xs text-gray-600">
        <Text k="inquiry.sender_ai" />
      </p>
      {noticeKey ? (
        <p>
          <Text k={noticeKey} />
        </p>
      ) : (
        // AI の答えは、辞書を通さず文字としてだけ出す（タグは実行されない。FR-028）
        <p className="whitespace-pre-wrap">{message.body}</p>
      )}
      {showsCallIfUrgent(message) && (
        <p className="mt-1 text-sm">
          <Text k="inquiry.call_if_urgent" />
        </p>
      )}
      {message.sources.length > 0 && (
        <div className="mt-2 text-sm text-gray-700">
          <p className="font-bold">
            <Text k="inquiry.source_records" />
          </p>
          <ul>
            {message.sources.map((source, index) => (
              <SourceItem key={index} source={source} />
            ))}
          </ul>
        </div>
      )}
      {/* AI の答えであることを、答えのそばに常に出す（FR-005） */}
      <p className="mt-2 text-xs text-gray-500">
        <Text k="inquiry.ai_notice" />
      </p>
    </li>
  )
}

function SourceItem({ source }: { source: InquirySource }) {
  const { t } = useTranslation()
  const { month, day, labelKeys } = sourceParts(source)
  return (
    <li>
      <Ruby text={t('inquiry.source_date', { month, day })} />
      {labelKeys.map((key) => (
        <span key={key}>
          ・<Text k={key} />
        </span>
      ))}
    </li>
  )
}

// 辞書の「{{name}}からの返事」を、名前の前と後ろに分けるための目印（名前には入らない文字）
const NAME_SLOT = '\u0000'

function StaffBubble({
  message,
  onSeen,
}: {
  message: InquiryMessage
  onSeen?: (messageId: number) => void
}) {
  const { t } = useTranslation()
  // 画面に出たら、その発言のお知らせを読んだことにする（電話で対応した発言は送らない）
  const ref = useOnVisible<HTMLLIElement>(
    onSeen && marksNoticeRead(message) ? () => onSeen(message.id) : null,
  )
  // 名前は辞書の文に差し込まず、文字のまま出す（名前の { | } を、ふりがなの書き方と取り違えないため。
  // 語順は辞書の文のまま使えるので、インドネシア語・英語でも同じ形で出せる。PR #213 さとこ）
  const [before, after = ''] = t('inquiry.reply_from', { name: NAME_SLOT }).split(NAME_SLOT)
  return (
    <li ref={ref} className="mr-8 rounded border border-emerald-300 bg-emerald-50 p-3">
      {/* 職員の返事は「◯◯からの返事」と、AI の答えと区別して出す（FR-005） */}
      <p className="text-xs text-gray-600">
        <Ruby text={before} />
        {message.staff_name}
        {/* 職種は辞書で引く（「山本（生活相談員）からの返事」。空なら名前だけ。#263） */}
        <OccupationLabel code={message.staff_occupation} />
        <Ruby text={after} />
      </p>
      {message.response_type === 'phone' ? (
        <p>
          <Text k="inquiry.staff_phone_response" />
        </p>
      ) : (
        <>
          {(message.template_codes ?? []).map((code) => (
            <p key={code}>
              <Text k={code} />
            </p>
          ))}
          {/* 職員が書き足した文は、辞書を通さず文字としてだけ出す（FR-028） */}
          {message.note && <p className="whitespace-pre-wrap">{message.note}</p>}
        </>
      )}
    </li>
  )
}
