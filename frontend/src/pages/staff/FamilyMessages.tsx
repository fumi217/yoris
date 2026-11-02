import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentFamily } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import {
  arrivedKey,
  categoryKey,
  listUrl,
  MESSAGES_KEY,
  messagesBase,
  residentFilterOf,
  STATUS_TABS,
  type MessageList,
  type MessageRow,
  type Status,
} from './messagesView'

/**
 * 職員の「家族からのメッセージ」の一覧（UI-S08。spec 004 の T029）。
 * 職員の画面（/staff/messages）と管理画面（/admin/messages）の両方から開く同じ画面。
 * 対応待ちを先に、担当が自分か空のものを先に、古い順（API が並べる。FR-012）。通知・音は出さない（FR-013）。
 */
export function FamilyMessages() {
  const { pathname, search } = useLocation()
  const base = messagesBase(pathname)
  // 入居者の一覧の「📩 ◯件」から来たときは、その入居者の分だけに絞る（`?resident_id=`。#88）
  const residentId = residentFilterOf(search)
  const [status, setStatus] = useState<Status>('waiting')
  const messages = useQuery({
    queryKey: [...MESSAGES_KEY, 'list', status, residentId],
    queryFn: () => api.get<MessageList>(listUrl(status, residentId)),
  })

  return (
    <section className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        <Text k="family_messages.title" />
      </h1>
      {residentId !== null && (
        <p className="flex flex-wrap items-center gap-x-3 rounded-lg border border-card-line bg-card p-3 text-sm">
          <span>
            <Text k="family_messages.filtered" />
          </span>
          <Link to={base} className="text-primary underline">
            <Text k="family_messages.show_all" />
          </Link>
        </p>
      )}
      <MessageTabs status={status} onChange={setStatus} />
      {messages.isPending ? (
        <Message k="layout.loading" />
      ) : messages.isError ? (
        <Message k={messageKeyOf(messages.error)} />
      ) : (
        <MessageListView
          base={base}
          status={status}
          messages={messages.data.messages}
          search={residentId === null ? '' : `?resident_id=${residentId}`}
        />
      )}
      <BackToResidents base={base} />
    </section>
  )
}

/**
 * 職員の画面で開いたときの「入居者一覧へ」（#256）。
 * 管理画面で開いたときは、枠の「管理画面のトップへ」があるので出さない。
 */
export function BackToResidents({ base }: { base: string }) {
  if (base !== '/staff/messages') return null
  return (
    <Link to="/staff" className="inline-block text-primary underline">
      <Text k="family_messages.back_to_residents" />
    </Link>
  )
}

function MessageTabs({ status, onChange }: { status: Status; onChange: (next: Status) => void }) {
  return (
    <div role="tablist" className="flex gap-2">
      {STATUS_TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          role="tab"
          aria-selected={status === tab}
          onClick={() => onChange(tab)}
          className={`min-h-12 flex-1 rounded border-2 p-2 ${
            status === tab ? 'border-primary bg-primary text-white' : 'border-field-line bg-white'
          }`}
        >
          <Text k={`family_messages.tab_${tab}`} />
        </button>
      ))}
    </div>
  )
}

/**
 * 一覧の中身（API の並びのまま出す。テストではこれを直接出す）。
 * search は、詳細へのリンクに引き継ぐ絞り込み（`?resident_id=3`）。詳細の「一覧へ」で戻ったとき絞り込みが残る。
 */
export function MessageListView({
  base,
  status,
  messages,
  search = '',
}: {
  base: string
  status: Status
  messages: MessageRow[]
  search?: string
}) {
  if (messages.length === 0) {
    return <Message k={`family_messages.empty_${status}`} />
  }
  return (
    <>
      <p className="text-xs text-gray-600">
        <Text k="family_messages.furigana_auto" />
      </p>
      <ul className="divide-y rounded border border-card-line">
        {messages.map((message) => (
          <li key={message.id}>
            <MessageItem base={base} message={message} search={search} />
          </li>
        ))}
      </ul>
    </>
  )
}

function MessageItem({
  base,
  message,
  search,
}: {
  base: string
  message: MessageRow
  search: string
}) {
  const { t } = useTranslation()
  return (
    <Link to={`${base}/${message.id}${search}`} className="block space-y-1 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-bold">
          <ResidentFamily
            name={message.resident_display_name}
            ruby={message.resident_display_name_ruby}
            relationship={message.family_relationship}
          />
          <span className="ml-2 rounded bg-gray-100 px-2 py-0.5 text-sm font-normal">
            <Text k={categoryKey(message.category)} />
          </span>
        </p>
        <p className="text-sm text-gray-600">
          <Ruby text={t(arrivedKey(message.elapsed_days), { count: message.elapsed_days })} />
        </p>
      </div>
      {/* AI の要約は、辞書を通さず、文字としてだけ出す（FR-028）。読みは自動で付けたもの（FR-028a） */}
      <p className="whitespace-pre-wrap">
        <Ruby text={message.summary_ruby} />
      </p>
      <p className="text-sm text-gray-600">
        {message.assignee ? (
          <>
            <Text k="family_messages.assignee" />：{message.assignee.display_name}
          </>
        ) : (
          <Text k="family_messages.unassigned" />
        )}
      </p>
    </Link>
  )
}
