import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useParams } from 'react-router'
import { ApiError, api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import {
  arrivedKey,
  canAssign,
  canReply,
  categoryKey,
  hasTemplates,
  MESSAGES_KEY,
  messagesBase,
  residentFilterOf,
  senderKey,
  type ConversationMessage,
  type MessageDetail,
} from './messagesView'
import { MAX_NOTE_LENGTH, noteLength, replyBody, toggleTemplate } from './replyForm'

/**
 * 職員の「家族からのメッセージ」の詳細（UI-S09。spec 004 の T029）。
 * 質問の原文・要約・種類・担当・直前の 3 往復・追加の書き込みを出し、「自分が対応する」と、
 * 定型文（1 つ以上）＋100 文字までの書き足しでの返事ができる（開いてから 3 タップ以内。SC-012）。
 * ほかの職員が先に担当になった・返事をした（409）ときは、文言を出して読み直す。
 */
export function FamilyMessage() {
  const { messageId = '' } = useParams()
  const { pathname, search } = useLocation()
  const base = messagesBase(pathname)
  // 絞り込んだ一覧から来たときは、「一覧へ」で戻っても絞り込みを残す（#88）
  const residentId = residentFilterOf(search)
  const backTo = residentId === null ? base : `${base}?resident_id=${residentId}`
  const queryClient = useQueryClient()
  const detailKey = [...MESSAGES_KEY, 'detail', messageId]

  const detail = useQuery({
    queryKey: detailKey,
    queryFn: () => api.get<MessageDetail>(`/api/staff/messages/${messageId}`),
  })

  // 担当や状態が変わると、一覧・件数・入居者一覧の件数も変わる
  const refresh = () =>
    Promise.all(
      [detailKey, MESSAGES_KEY, ['staff', 'residents']].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    )
  const onError = (error: unknown) => {
    if (error instanceof ApiError && error.status === 409) void refresh()
  }
  const assign = useMutation({
    mutationFn: () => api.post(`/api/staff/messages/${messageId}/assign`),
    onSuccess: refresh,
    onError,
  })
  const reply = useMutation({
    mutationFn: ({ templateIds, note }: { templateIds: number[]; note: string }) =>
      api.post(`/api/staff/messages/${messageId}/reply`, replyBody(templateIds, note)),
    onSuccess: refresh,
    onError,
  })

  if (detail.isPending) return <Message k="layout.loading" />
  // 見られないメッセージ（ほかの役割の苦情・ないもの）は 404。「見つかりませんでした」と出す
  if (detail.isError) return <Message k={messageKeyOf(detail.error)} />
  const errorKey = assign.isError
    ? messageKeyOf(assign.error)
    : reply.isError
      ? messageKeyOf(reply.error)
      : null
  return (
    <MessageDetailView
      backTo={backTo}
      message={detail.data}
      assigning={assign.isPending}
      sending={reply.isPending}
      errorKey={errorKey}
      onAssign={() => assign.mutate()}
      onReply={(value) => reply.mutate(value)}
    />
  )
}

type ViewProps = {
  /** 「一覧へ」の行き先。絞り込んだ一覧から来たときは、絞り込みを付けたもの */
  backTo: string
  message: MessageDetail
  assigning: boolean
  sending: boolean
  errorKey: string | null
  onAssign: () => void
  onReply: (value: { templateIds: number[]; note: string }) => void
}

/** 詳細の中身（テストではこれを直接出す）。 */
export function MessageDetailView({
  backTo,
  message,
  assigning,
  sending,
  errorKey,
  onAssign,
  onReply,
}: ViewProps) {
  const { t } = useTranslation()
  return (
    <section className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        {/* 入居者の呼び名は、辞書を通さずそのまま出す */}
        {message.resident_display_name}
        <span className="ml-2 rounded bg-gray-100 px-2 py-0.5 text-base font-normal">
          <Text k={categoryKey(message.category)} />
        </span>
      </h1>

      <p className="flex flex-wrap items-baseline gap-x-4 text-sm text-gray-600">
        <span>
          <Text k={`family_messages.status_${message.status}`} />
        </span>
        <span>
          <Ruby text={t(arrivedKey(message.elapsed_days), { count: message.elapsed_days })} />
        </span>
        <span>
          {message.assignee ? (
            <>
              <Text k="family_messages.assignee" />：{message.assignee.display_name}
            </>
          ) : (
            <Text k="family_messages.unassigned" />
          )}
        </span>
      </p>

      {errorKey && (
        <p role="alert" className="rounded border border-red-700 p-3 text-red-700">
          <Text k={errorKey} />
        </p>
      )}

      <p className="text-xs text-gray-600">
        <Text k="family_messages.furigana_auto" />
      </p>
      <Block titleKey="family_messages.origin_title">
        <Bubble message={message.origin} bodyRuby={message.origin_ruby} />
      </Block>
      <Block titleKey="family_messages.summary_title">
        {/* AI の要約は、辞書を通さず、文字としてだけ出す（FR-028）。読みは自動で付けたもの（FR-028a） */}
        <p className="whitespace-pre-wrap rounded-lg border border-card-line bg-card p-3">
          <Ruby text={message.summary_ruby} />
        </p>
      </Block>
      {message.previous.length > 0 && (
        <Block titleKey="family_messages.previous_title">
          <Conversation messages={message.previous} />
        </Block>
      )}
      {message.follow_ups.length > 0 && (
        <Block titleKey="family_messages.follow_ups_title">
          <Conversation messages={message.follow_ups} />
        </Block>
      )}

      {canAssign(message) && (
        <button
          type="button"
          disabled={assigning}
          onClick={onAssign}
          className="w-full rounded border-2 border-primary p-3 text-lg font-bold text-primary disabled:opacity-50"
        >
          <Text k={assigning ? 'family_messages.assigning' : 'family_messages.assign'} />
        </button>
      )}

      {canReply(message) ? (
        <ReplyForm templates={message.templates} sending={sending} onSend={onReply} />
      ) : (
        <p className="rounded-lg border border-card-line bg-card p-3 text-center">
          <Text k="family_messages.answered_done" />
        </p>
      )}

      <Link to={backTo} className="inline-block text-primary underline">
        <Text k="family_messages.back" />
      </Link>
    </section>
  )
}

function Block({ titleKey, children }: { titleKey: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <h2 className="text-sm font-bold text-gray-700">
        <Text k={titleKey} />
      </h2>
      {children}
    </div>
  )
}

function Conversation({ messages }: { messages: ConversationMessage[] }) {
  return (
    <ol className="space-y-2">
      {messages.map((message) => (
        <li key={message.id}>
          <Bubble message={message} />
        </li>
      ))}
    </ol>
  )
}

/**
 * 発言 1 つ。家族・AI・職員の文は、辞書を通さず、文字としてだけ出す（FR-028）。
 * bodyRuby があるとき（質問の原文だけ）は、読みを付けた文を `Ruby` で出す（FR-028a）。
 */
function Bubble({ message, bodyRuby }: { message: ConversationMessage; bodyRuby?: string }) {
  return (
    <div className="space-y-1 rounded border border-card-line p-3">
      <p className="text-xs text-gray-600">
        <Text k={senderKey(message.sender)} />
      </p>
      {message.body !== '' && (
        <p className="whitespace-pre-wrap">
          {bodyRuby === undefined ? message.body : <Ruby text={bodyRuby} />}
        </p>
      )}
      {message.template_codes?.map((code) => (
        <p key={code}>
          <Text k={code} />
        </p>
      ))}
      {message.note && <p className="whitespace-pre-wrap">{message.note}</p>}
    </div>
  )
}

type ReplyFormProps = {
  templates: MessageDetail['templates']
  sending: boolean
  onSend: ViewProps['onReply']
}

function ReplyForm({ templates, sending, onSend }: ReplyFormProps) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<number[]>([])
  const [note, setNote] = useState('')
  const tooLong = noteLength(note) > MAX_NOTE_LENGTH

  // 苦情には定型文がない。電話で対応する（FR-014）
  if (!hasTemplates(templates)) {
    return (
      <p className="rounded border border-card-line p-3">
        <Text k="family_messages.no_templates" />
      </p>
    )
  }
  return (
    <form
      className="space-y-3 rounded border-2 border-field-line p-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSend({ templateIds: selected, note })
      }}
    >
      <h2 className="text-lg font-bold">
        <Text k="family_messages.reply_title" />
      </h2>
      <fieldset>
        <legend className="mb-2 text-sm">
          <Text k="family_messages.choose" />
        </legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {templates.map((template) => {
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
        <Text k="family_messages.note" />
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
          {t('family_messages.note_count', { count: noteLength(note) })}
        </span>
      </label>
      <button
        type="submit"
        disabled={selected.length === 0 || tooLong || sending}
        className="w-full rounded bg-primary p-3 text-lg font-bold text-white disabled:opacity-50"
      >
        <Text k={sending ? 'family_messages.sending' : 'family_messages.send'} />
      </button>
    </form>
  )
}
