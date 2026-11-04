import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useParams } from 'react-router'
import { ApiError, api, messageKeyOf } from '../../api/client'
import { Icon } from '../../components/Icon'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentFamily } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import {
  arrivedKey,
  canAssign,
  canReply,
  hasTemplates,
  MESSAGES_KEY,
  messagesBase,
  residentFilterOf,
  senderKey,
  type ConversationMessage,
  type MessageDetail,
} from './messagesView'
import { AssigneeLabel, CategoryLabel } from './FamilyMessages'
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
      <Link
        to={backTo}
        className="-my-2 inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary"
      >
        <Icon name="prev" />
        <Text k="family_messages.back" />
      </Link>

      {/* 見出しの面：だれからか・種類・状態・届いてからの日数・担当（#441） */}
      <div className="space-y-2.5 rounded-2xl border border-card-line bg-card p-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="text-[22px] font-bold">
            <ResidentFamily
              name={message.resident_display_name}
              ruby={message.resident_display_name_ruby}
              relationship={message.family_relationship}
            />
          </h1>
          <CategoryLabel category={message.category} />
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-ink-sub">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
              message.status === 'waiting'
                ? 'bg-red-100 text-red-800'
                : 'bg-green-100 text-green-800'
            }`}
          >
            <Text k={`family_messages.status_${message.status}`} />
          </span>
          <span>
            <Icon name="upload-waiting" className="mr-1" />
            <Ruby text={t(arrivedKey(message.elapsed_days), { count: message.elapsed_days })} />
          </span>
          <AssigneeLabel assignee={message.assignee} />
        </div>
        {message.waiting_over_a_day && (
          <p className="text-sm font-bold text-amber-800">
            <Icon name="warning" className="mr-1" />
            <Text k="family_messages.waiting_over_day" />
          </p>
        )}
      </div>

      {errorKey && (
        <p
          role="alert"
          className="rounded-2xl border border-red-700 bg-card p-3 font-bold text-red-700"
        >
          <Text k={errorKey} />
        </p>
      )}

      <p className="flex items-center gap-1.5 text-sm text-ink-sub">
        <Icon name="info" className="shrink-0" />
        <Text k="family_messages.furigana_auto" />
      </p>
      <Block titleKey="family_messages.origin_title">
        <div className="flex justify-end">
          <Bubble message={message.origin} bodyRuby={message.origin_ruby} />
        </div>
      </Block>
      <Block titleKey="family_messages.summary_title">
        {/* AI の要約は、辞書を通さず、文字としてだけ出す（FR-028）。読みは自動で付けたもの（FR-028a） */}
        <p className="whitespace-pre-wrap rounded-2xl bg-primary-soft px-4 py-3 leading-relaxed">
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
          className="flex min-h-13 w-full items-center justify-center gap-2 rounded-2xl border-2 border-primary bg-card p-3 text-lg font-bold text-primary-dark disabled:opacity-50"
        >
          <Icon name="staff-account" />
          <Text k={assigning ? 'family_messages.assigning' : 'family_messages.assign'} />
        </button>
      )}

      {canReply(message) ? (
        <ReplyForm templates={message.templates} sending={sending} onSend={onReply} />
      ) : (
        <p className="rounded-2xl bg-green-100 p-3 text-center font-bold text-green-800">
          <Icon name="check" className="mr-1" />
          <Text k="family_messages.answered_done" />
        </p>
      )}
    </section>
  )
}

function Block({ titleKey, children }: { titleKey: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <h2 className="ml-1 text-sm font-bold text-ink-sub">
        <Text k={titleKey} />
      </h2>
      {children}
    </div>
  )
}

function Conversation({ messages }: { messages: ConversationMessage[] }) {
  return (
    <ol className="flex flex-col gap-2.5">
      {messages.map((message) => (
        <li key={message.id} className={`flex ${message.sender === 'family' ? 'justify-end' : ''}`}>
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
// 発言の吹き出しの色：家族は白（右寄せ）、AI は薄い青の枠、職員は「成功」の色
const BUBBLE: Record<ConversationMessage['sender'], string> = {
  family: 'rounded-tr-sm border border-card-line bg-card',
  ai: 'rounded-tl-sm border-2 border-primary-soft bg-card',
  staff: 'rounded-tl-sm bg-green-100',
}

function Bubble({ message, bodyRuby }: { message: ConversationMessage; bodyRuby?: string }) {
  return (
    // だれの発言かは、位置と色に加えて、上の文字（ご家族・AI・職員）でも示す（1.3.1・1.4.1）
    <div className={`max-w-[88%] space-y-1 rounded-2xl px-4 py-2.5 ${BUBBLE[message.sender]}`}>
      <p className="text-xs font-bold text-ink-sub">
        <Text k={senderKey(message.sender)} />
      </p>
      {message.body !== '' && (
        <p className="whitespace-pre-wrap leading-relaxed">
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
      <p className="rounded-2xl border border-card-line bg-card p-3">
        <Icon name="urgent-call" className="mr-1 text-primary" />
        <Text k="family_messages.no_templates" />
      </p>
    )
  }
  return (
    <form
      className="space-y-3 rounded-2xl border border-card-line bg-card p-4"
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
                // 選んだ定型文は、薄い青の背景・枠・✔ と aria-pressed で示す（色だけに頼らない）
                className={`flex min-h-14 items-center gap-2 rounded-2xl border-2 px-3 py-2 text-left font-bold ${
                  on
                    ? 'border-primary bg-primary-soft text-primary-dark'
                    : 'border-field-line bg-card'
                }`}
              >
                {on && <Icon name="check" className="shrink-0" />}
                <Text k={template.code} />
              </button>
            )
          })}
        </div>
      </fieldset>
      <label className="block text-sm font-bold">
        <Text k="family_messages.note" />
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          aria-invalid={tooLong}
          className="mt-1 block w-full rounded-xl border border-field-line bg-card p-3 text-base aria-[invalid=true]:border-2 aria-[invalid=true]:border-red-700"
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
        className="flex min-h-13 w-full items-center justify-center gap-2 rounded-2xl bg-primary p-3 text-lg font-bold text-white disabled:opacity-50"
      >
        <Icon name="send" />
        <Text k={sending ? 'family_messages.sending' : 'family_messages.send'} />
      </button>
    </form>
  )
}
