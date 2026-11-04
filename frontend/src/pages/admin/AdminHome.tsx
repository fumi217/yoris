import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api } from '../../api/client'
import { useMe, type StaffRole } from '../../auth/me'
import { Icon, type IconName } from '../../components/Icon'
import { Message } from '../../components/Message'
import { ResidentFamily } from '../../components/ResidentName'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import { endOf, hhmm } from '../family/visits/visitDates'
import { CategoryLabel } from '../staff/FamilyMessages'
import {
  arrivedKey,
  listUrl,
  MESSAGES_KEY,
  type MessageList,
  type MessageRow,
} from '../staff/messagesView'
import { RoomTile } from '../staff/TodayVisits'
import { useMemoApprovalCount } from '../staff/useMemoApprovalCount'
import { useTodayVisits } from '../staff/useTodayVisits'
import { useWaitingMessageCount } from '../staff/useWaitingMessageCount'
import type { StaffReservation } from '../staff/visitReservationRows'
import { adminMenuFor } from './adminMenu'
import { hiddenLabels } from './adminHomeView'
import type { Disclosure } from './DisclosureSettings'

// 開示設定を開ける役割（API の DISCLOSURE_EDITORS と同じ。ほかの役割は読まない）
const DISCLOSURE_ROLES: StaffRole[] = ['counselor', 'director']
// トップに出す、対応待ちのメッセージの数（古いものから。全部は一覧の画面で見る）
const MESSAGE_PREVIEW = 3

/**
 * 管理画面のトップ（UI-A00。#451）＝「今日の状況」。
 * 上に数の札（対応待ちのメッセージ・今日の面会・様子のメモの承認待ち・家族に見せていない項目）、
 * その下に中身の短い一覧。押すと、それぞれの画面へ。行き先の一覧は、上のタブ（#437）に任せる。
 * 数は今ある API で数える。役割で開けないものは出さない（守りは API の 403）。通知・音は出さない。
 */
export function AdminHome() {
  const role = useMe().data?.role ?? null
  const canDisclose = role !== null && DISCLOSURE_ROLES.includes(role)
  const messageCount = useWaitingMessageCount()
  const messages = useQuery({
    queryKey: [...MESSAGES_KEY, 'list', 'waiting', null],
    queryFn: () => api.get<MessageList>(listUrl('waiting', null)),
  })
  const visits = useTodayVisits()
  const memoCount = useMemoApprovalCount()
  const disclosure = useQuery({
    queryKey: ['admin', 'disclosure'],
    queryFn: () => api.get<Disclosure>('/api/admin/disclosure'),
    enabled: canDisclose,
  })

  if (adminMenuFor(role).length === 0) return <Message k="admin.no_menu" />
  return (
    <AdminHomeView
      messageCount={messageCount}
      messages={messages.data?.messages ?? null}
      visits={visits.data ?? null}
      memoCount={memoCount}
      disclosure={canDisclose ? (disclosure.data ?? null) : undefined}
    />
  )
}

type ViewProps = {
  messageCount: number
  // まだ読めていない・読めないときは null（一覧は出さず、数だけ出す）
  messages: MessageRow[] | null
  visits: StaffReservation[] | null
  // 承認できない人・読めないときは null（札を出さない）
  memoCount: number | null
  // 開示設定を開けない人は undefined（札も一覧も出さない）。読み込み中は null
  disclosure?: Disclosure | null
}

/** 中身（テストではこれを直接出す）。 */
export function AdminHomeView({
  messageCount,
  messages,
  visits,
  memoCount,
  disclosure,
}: ViewProps) {
  const { t } = useTranslation()
  const late = messages?.some((message) => message.waiting_over_a_day) ?? false
  const hidden = disclosure ? hiddenLabels(disclosure) : null
  const nextVisit = visits?.[0]

  return (
    <section className="space-y-4 p-4">
      <div>
        <h1 className="text-2xl font-bold">
          <Text k="admin.today_title" />
        </h1>
        <p className="mt-1 text-sm text-ink-sub">
          <Text k="admin.today_lead" />
        </p>
      </div>

      <div className="grid gap-2.5 min-[480px]:grid-cols-2">
        <Stat
          to="/admin/messages"
          icon="family-message"
          labelKey="admin.kpi.messages"
          value={messageCount}
          unitKey="resident_list.unit_cases"
          urgent={late}
          sub={<Text k={late ? 'admin.kpi.over_day' : 'admin.kpi.messages_sub'} />}
        />
        <Stat
          to="/admin/visits"
          icon="visits"
          labelKey="admin.kpi.visits"
          value={visits?.length ?? null}
          unitKey="resident_list.unit_groups"
          sub={
            nextVisit ? (
              <Ruby text={t('admin.kpi.next_visit', { time: hhmm(nextVisit.start_time) })} />
            ) : (
              <Text k="admin.kpi.no_visit" />
            )
          }
        />
        {memoCount !== null && (
          // 承認は職員の画面で行う（リーダー・施設長。管理画面では施設長だけに出る）
          <Stat
            to="/staff/memo-approvals"
            icon="memo"
            labelKey="admin.kpi.memos"
            value={memoCount}
            unitKey="resident_list.unit_cases"
            sub={<Text k="admin.kpi.memos_sub" />}
          />
        )}
        {disclosure !== undefined && (
          <Stat
            to="/admin/disclosure"
            icon="disclosure"
            labelKey="admin.kpi.hidden"
            value={hidden?.length ?? null}
            unitKey="resident_list.unit_cases"
            sub={
              hidden && hidden.length === 0 ? (
                <Text k="admin.kpi.hidden_none" />
              ) : (
                hidden && <Ruby text={hidden.map((label) => t(label.key)).join('・')} />
              )
            }
          />
        )}
      </div>

      <Panel
        icon="family-message"
        titleKey="admin.kpi.messages"
        moreTo="/admin/messages"
        moreKey="admin.see_all"
      >
        {messages === null ? null : messages.length === 0 ? (
          <p className="px-4 py-3 text-sm text-ink-sub">
            <Text k="admin.messages_empty" />
          </p>
        ) : (
          <ul>
            {messages.slice(0, MESSAGE_PREVIEW).map((message) => (
              <li key={message.id} className="border-t border-card-line first:border-t-0">
                <Link
                  to={`/admin/messages/${message.id}`}
                  className="flex min-h-14 items-center gap-3 px-4 py-2.5 hover:bg-primary-soft"
                >
                  <span className="min-w-0 flex-1">
                    <span className="font-bold">
                      <ResidentFamily
                        name={message.resident_display_name}
                        ruby={message.resident_display_name_ruby}
                        relationship={message.family_relationship}
                      />
                    </span>
                    <span className="ml-2 align-middle">
                      <CategoryLabel category={message.category} />
                    </span>
                    <span
                      className={`block text-sm ${message.waiting_over_a_day ? 'font-bold text-amber-800' : 'text-ink-sub'}`}
                    >
                      {message.waiting_over_a_day && <Icon name="warning" className="mr-1" />}
                      <Ruby
                        text={t(
                          message.waiting_over_a_day
                            ? 'family_messages.waiting_over_day'
                            : arrivedKey(message.elapsed_days),
                          { count: message.elapsed_days },
                        )}
                      />
                      <span className="mx-1">・</span>
                      {message.assignee ? (
                        <>
                          <Text k="family_messages.assignee" />：{message.assignee.display_name}
                        </>
                      ) : (
                        <Text k="family_messages.unassigned" />
                      )}
                    </span>
                  </span>
                  <Icon name="next" className="text-ink-sub" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="grid gap-4 sm:grid-cols-2">
        <Panel
          icon="visits"
          titleKey="admin.kpi.visits"
          moreTo="/admin/visits"
          moreKey="admin.to_visits"
        >
          {visits === null ? null : visits.length === 0 ? (
            <p className="px-4 py-3 text-sm text-ink-sub">
              <Text k="visit_list.today_empty" />
            </p>
          ) : (
            <ol>
              {visits.map((row) => {
                const start = hhmm(row.start_time)
                return (
                  <li
                    key={row.id}
                    className="flex items-center gap-3 border-t border-card-line px-4 py-2.5 first:border-t-0"
                  >
                    <span className="w-14 shrink-0 leading-tight tabular-nums">
                      <span className="block text-lg font-bold">{start}</span>
                      <span className="text-xs text-ink-sub">〜{endOf(start)}</span>
                    </span>
                    <RoomTile room={row.room} />
                    <span className="min-w-0 flex-1 text-sm">
                      <span className="block font-bold">
                        <ResidentFamily
                          name={row.resident_name}
                          ruby={row.resident_name_ruby}
                          relationship={null}
                        />
                      </span>
                      <span className="text-ink-sub">
                        <Ruby text={t('visit.visitors', { count: row.party_size })} />
                      </span>
                    </span>
                  </li>
                )
              })}
            </ol>
          )}
        </Panel>

        {disclosure !== undefined && (
          <Panel
            icon="disclosure"
            titleKey="admin.panel_hidden"
            moreTo="/admin/disclosure"
            moreKey="admin.to_disclosure"
          >
            {hidden === null ? null : hidden.length === 0 ? (
              <p className="px-4 py-3 text-sm text-ink-sub">
                <Text k="admin.kpi.hidden_none" />
              </p>
            ) : (
              <ul className="flex flex-wrap gap-2 px-4 py-3">
                {hidden.map((label) => (
                  <li
                    key={label.key}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-card-line bg-page px-2.5 py-1 text-sm font-bold text-ink-sub"
                  >
                    <Icon name={label.icon} />
                    <Text k={label.key} />
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        )}
      </div>
    </section>
  )
}

/** 数の札（押すと、その画面へ）。急ぐものは、注意の色の左の線と文字で示す（色だけに頼らない）。 */
function Stat({
  to,
  icon,
  labelKey,
  value,
  unitKey,
  sub,
  urgent = false,
}: {
  to: string
  icon: IconName
  labelKey: string
  // 読めていないときは null（「—」を出す）
  value: number | null
  unitKey: string
  sub: ReactNode
  urgent?: boolean
}) {
  const { t } = useTranslation()
  return (
    <Link
      to={to}
      className={`flex flex-col gap-1 rounded-xl border bg-card px-4 py-3 hover:border-primary ${
        urgent
          ? 'border-amber-300 shadow-[inset_3px_0_0_var(--color-amber-800)]'
          : 'border-card-line'
      }`}
    >
      <span className="flex items-center gap-2 text-sm font-bold text-ink-sub">
        <Icon name={icon} className="text-primary" />
        <Text k={labelKey} />
      </span>
      <span className="text-3xl leading-tight font-extrabold tabular-nums">
        {value ?? '—'}
        <small className="ml-1 text-base font-bold">
          <Text k={unitKey} />
        </small>
        {/* 読み上げでは、数だけにならないよう、何の数かを添える */}
        <span className="sr-only">{stripRuby(t(labelKey))}</span>
      </span>
      <span className={`text-sm ${urgent ? 'font-bold text-amber-800' : 'text-ink-sub'}`}>
        {urgent && <Icon name="warning" className="mr-1" />}
        {sub}
      </span>
    </Link>
  )
}

/** 中身の短い一覧の白い面（見出し・「すべて」へのリンク）。 */
function Panel({
  icon,
  titleKey,
  moreTo,
  moreKey,
  children,
}: {
  icon: IconName
  titleKey: string
  moreTo: string
  moreKey: string
  children: ReactNode
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-card-line bg-card">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-card-line px-4 py-2.5">
        <h2 className="flex-1 font-bold">
          <Icon name={icon} className="mr-2 text-primary" />
          <Text k={titleKey} />
        </h2>
        <Link
          to={moreTo}
          className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary"
        >
          <Text k={moreKey} />
          <Icon name="next" />
        </Link>
      </div>
      {children}
    </section>
  )
}
