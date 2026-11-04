import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Icon } from '../../components/Icon'
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
      <h1 className="text-2xl font-bold">
        <Text k="family_messages.title" />
      </h1>
      {residentId !== null && (
        <p className="flex flex-wrap items-center gap-x-3 rounded-2xl border border-card-line bg-card p-3 text-sm">
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
    <Link
      to="/staff"
      className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary"
    >
      <Icon name="prev" />
      <Text k="family_messages.back_to_residents" />
    </Link>
  )
}

function MessageTabs({ status, onChange }: { status: Status; onChange: (next: Status) => void }) {
  return (
    // 丸い切り替え（記録の画面の区分と同じ形。#441）。選ばれたものは、塗りと太字で示す
    <div
      role="tablist"
      className="grid auto-cols-fr grid-flow-col gap-1 rounded-full border border-card-line bg-card p-1"
    >
      {STATUS_TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          role="tab"
          aria-selected={status === tab}
          onClick={() => onChange(tab)}
          className={`min-h-11 rounded-full px-3 ${
            status === tab ? 'bg-primary font-bold text-white' : 'font-semibold text-ink-sub'
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
      <p className="flex items-center gap-1.5 text-sm text-ink-sub">
        <Icon name="info" className="shrink-0" />
        <Text k="family_messages.furigana_auto" />
      </p>
      <ul className="overflow-hidden rounded-2xl border border-card-line bg-card">
        {messages.map((message) => (
          <li key={message.id} className="border-t border-card-line first:border-t-0">
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
  const waiting = message.status === 'waiting'
  return (
    // 対応待ちは、左の線で目立たせる（色だけでなく、上のタブと「担当なし」の文字でも分かる）。
    // 行の背景は白のまま（薄い青はページの背景とほぼ同じ色で、行が溶けて見えるため。PR #444 ようこさん）
    <Link
      to={`${base}/${message.id}${search}`}
      className={`block space-y-1.5 px-4 py-3.5 hover:bg-primary-soft ${
        waiting ? 'shadow-[inset_4px_0_0_var(--color-primary)]' : ''
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <p className="text-[17px] font-bold">
          <ResidentFamily
            name={message.resident_display_name}
            ruby={message.resident_display_name_ruby}
            relationship={message.family_relationship}
          />
        </p>
        <CategoryLabel category={message.category} />
        {/* アイコンと文字は 1 つの行に入れる（flex だと、ふりがなの分だけアイコンが浮く。PR #444 ようこさん） */}
        <p className="ml-auto text-sm text-ink-sub">
          <Icon name="upload-waiting" className="mr-1" />
          <Ruby text={t(arrivedKey(message.elapsed_days), { count: message.elapsed_days })} />
        </p>
      </div>
      {/* 渡してから 24 時間たっても対応待ち。色だけでなく、印と文字で目立たせる（FR-016b） */}
      {message.waiting_over_a_day && (
        <p className="text-sm font-bold text-amber-800">
          <Icon name="warning" className="mr-1" />
          <Text k="family_messages.waiting_over_day" />
        </p>
      )}
      {/* AI の要約は、辞書を通さず、文字としてだけ出す（FR-028）。読みは自動で付けたもの（FR-028a） */}
      <p className="whitespace-pre-wrap leading-relaxed">
        <Ruby text={message.summary_ruby} />
      </p>
      <div className="flex items-center justify-between gap-2">
        <AssigneeLabel assignee={message.assignee} />
        <Icon name="next" className="text-ink-sub" />
      </div>
    </Link>
  )
}

// 急ぎ・体調・苦情は、目立つ色（警告）。ほかは落ち着いた色。どちらも文字で種類を出す（色だけに頼らない）
const URGENT_CATEGORIES: MessageRow['category'][] = ['urgent', 'medical', 'complaint']

/** 質問の種類の丸いラベル（一覧・詳細で同じ）。 */
export function CategoryLabel({ category }: { category: MessageRow['category'] }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold ${
        URGENT_CATEGORIES.includes(category) ? 'bg-red-100 text-red-800' : 'bg-page text-ink-sub'
      }`}
    >
      <Text k={categoryKey(category)} />
    </span>
  )
}

/** 担当の丸いラベル（一覧・詳細で同じ）。いないときは、点線の「担当なし」。 */
export function AssigneeLabel({ assignee }: { assignee: MessageRow['assignee'] }) {
  return assignee ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary-soft px-2.5 py-0.5 text-sm font-bold text-primary-dark">
      <Icon name="staff-account" />
      <Text k="family_messages.assignee" />：{assignee.display_name}
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full border border-dashed border-field-line px-2.5 py-0.5 text-sm text-ink-sub">
      <Text k="family_messages.unassigned" />
    </span>
  )
}
