import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { Icon } from '../../components/Icon'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { SentRequestCard } from './SentRequestCard'
import { ThemeCard } from './ThemeCard'
import {
  cancelErrorKey,
  remainingSlots,
  SendStopped,
  sendErrorKey,
  sentBeforeStop,
  sentThemeIdsBeforeStop,
  toggleTheme,
  waitingThemeIds,
  type FamilyRequest,
  type FamilyTheme,
} from './requestsView'

const THEMES_KEY = ['family-themes'] as const
const REQUESTS_KEY = ['family-requests'] as const

/**
 * 「知りたいこと」を頼む画面と、送ったリクエストの一覧（UI-F03。001-T060）。
 * 見た目は #385 で刷新：テーマを選べるカードにし、返事待ちの空き（最大 3 件。FR-014）まで、複数選んで一度に送れる。
 * API は 1 件ずつなので、選んだ順に 1 件ずつ送り、途中で止まったら、残りは送らない。
 */
export function Requests() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<number[]>([])
  const [errorKey, setErrorKey] = useState<string | null>(null)
  // 送れた件数（成功の案内と、途中で止まったときの案内に使う）
  const [sentCount, setSentCount] = useState<number | null>(null)
  // 途中で止まったとき、送れたテーマの id（名前で案内する）
  const [sentThemeIds, setSentThemeIds] = useState<number[]>([])

  const themes = useQuery({
    queryKey: THEMES_KEY,
    queryFn: () => api.get<FamilyTheme[]>('/api/family/themes'),
  })
  const requests = useQuery({
    queryKey: REQUESTS_KEY,
    queryFn: () => api.get<FamilyRequest[]>('/api/family/requests'),
  })

  const send = useMutation({
    mutationFn: async (themeIds: number[]) => {
      const sentIds: number[] = []
      for (const themeId of themeIds) {
        try {
          await api.post('/api/family/requests', { theme_id: themeId })
        } catch (error) {
          throw new SendStopped(sentIds.length, error, sentIds)
        }
        sentIds.push(themeId)
      }
      return sentIds.length
    },
    onSuccess: (sent) => {
      setSelected([])
      setErrorKey(null)
      setSentCount(sent)
      setSentThemeIds([])
    },
    onError: (error) => {
      // 選んだテーマが残ると、そのまま「送る」を押し直してしまうので外す
      setSelected([])
      setErrorKey(sendErrorKey(error))
      setSentCount(sentBeforeStop(error))
      setSentThemeIds(sentThemeIdsBeforeStop(error))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: REQUESTS_KEY }),
  })

  const cancel = useMutation({
    mutationFn: (requestId: number) => api.delete(`/api/family/requests/${requestId}`),
    onSuccess: () => setErrorKey(null),
    onError: (error) => {
      setSentCount(null)
      setErrorKey(cancelErrorKey(error))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: REQUESTS_KEY }),
  })

  if (themes.isPending || requests.isPending) return <Message k="layout.loading" />
  if (themes.isError) return <Message k={messageKeyOf(themes.error)} />
  if (requests.isError) return <Message k={messageKeyOf(requests.error)} />

  return (
    <RequestsView
      themes={themes.data}
      requests={requests.data}
      selected={selected}
      sending={send.isPending}
      cancelling={cancel.isPending}
      errorKey={errorKey}
      sentCount={sentCount}
      sentThemeIds={sentThemeIds}
      onToggle={(themeId) => {
        setSentCount(null)
        setErrorKey(null)
        setSelected((current) => toggleTheme(current, themeId, remainingSlots(requests.data)))
      }}
      onSend={() => send.mutate(selected)}
      onCancel={(requestId) => cancel.mutate(requestId)}
    />
  )
}

type ViewProps = {
  themes: FamilyTheme[]
  requests: FamilyRequest[]
  selected: number[]
  sending: boolean
  cancelling: boolean
  errorKey: string | null
  // 直前に送れた件数（成功・途中で止まったときの案内。null は何も出さない）
  sentCount: number | null
  // 途中で止まったとき、送れたテーマの id（名前で案内する。なければ件数で案内する）
  sentThemeIds?: number[]
  onToggle: (themeId: number) => void
  onSend: () => void
  onCancel: (requestId: number) => void
}

/** 画面の見た目（API を呼ばない。テストではこれを描く）。 */
export function RequestsView({
  themes,
  requests,
  selected,
  sending,
  cancelling,
  errorKey,
  sentCount,
  sentThemeIds = [],
  onToggle,
  onSend,
  onCancel,
}: ViewProps) {
  const { t } = useTranslation()
  const waiting = waitingThemeIds(requests)
  const remaining = remainingSlots(requests)
  const left = remaining - selected.length
  const full = left <= 0

  return (
    <div className="space-y-8 p-4">
      <section className="space-y-4">
        <div className="space-y-1">
          <h1 className="text-xl font-bold sm:text-2xl">
            <Text k="requests.choose_title" />
          </h1>
          <p className="text-ink-sub">
            <Text k="requests.choose_sub" />
          </p>
        </div>

        {/* 返事待ちが上限で、空きがないとき：押せないカードの理由を、見出しのすぐ下に出す
            （スマホで、下までスクロールしないと見えないため。PR #387 ようこさん） */}
        {remaining === 0 && (
          <p role="status" className="rounded-xl bg-[#fef3c7] p-3 text-sm font-bold text-[#92400e]">
            <Text k="requests.full" />
          </p>
        )}

        <ul className="grid auto-rows-fr grid-cols-1 gap-3 sm:grid-cols-2">
          {themes.map((theme) => (
            <li key={theme.id} className="flex">
              <ThemeCard
                theme={theme}
                selected={selected.includes(theme.id)}
                waiting={waiting.has(theme.id)}
                full={full}
                onToggle={() => onToggle(theme.id)}
              />
            </li>
          ))}
        </ul>

        {/* 送信エリア（カードにしない軽い 1 行）：左に選んでいる状況、右に送る操作（役割を分ける） */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-card-line pt-4">
          <div className="space-y-1">
            <p className="flex items-center gap-2 font-bold" aria-live="polite">
              <Icon name="selected-count" className="text-primary" />
              {selected.length > 0 ? (
                <Ruby text={t('requests.selected_count', { count: selected.length })} />
              ) : (
                <Text k="requests.none_selected" />
              )}
            </p>
            {/* 空きがないときの理由は、上（見出しの下）に出すので、ここは出さない */}
            {remaining > 0 && (
              <p className="text-sm text-ink-sub">
                <Ruby text={t('requests.can_select', { count: Math.max(left, 0) })} />
              </p>
            )}
          </div>
          <button
            type="button"
            disabled={selected.length === 0 || sending}
            aria-busy={sending}
            onClick={onSend}
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-primary px-5 font-bold text-white disabled:bg-primary-soft disabled:text-ink-sub"
          >
            <Icon name="send" />
            <Text k="requests.send_all" />
          </button>
        </div>

        <div role="status">
          {sentCount !== null && sentCount > 0 && !errorKey && (
            <p className="font-bold">
              <Ruby text={t('requests.sent_done', { count: sentCount })} />
            </p>
          )}
        </div>
        {errorKey && (
          <div role="alert" className="space-y-1 text-red-700">
            {sentCount !== null && sentCount > 0 && (
              <p>
                <Ruby text={partialText(t, themes, sentThemeIds, sentCount)} />
              </p>
            )}
            <p>
              <Text k={errorKey} />
            </p>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">
          <Text k="requests.list_title" />
        </h2>
        {requests.length === 0 ? (
          <p className="text-ink-sub">
            <Text k="requests.empty" />
          </p>
        ) : (
          <ul className="space-y-3">
            {requests.map((request) => (
              <SentRequestCard
                key={request.id}
                request={request}
                cancelling={cancelling}
                onCancel={() => onCancel(request.id)}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/**
 * 途中で止まったときの案内。送れたテーマの名前が分かれば、「『普段の様子』は送れましたが、残りは送れませんでした」。
 * 名前が分からないときは、件数で案内する。
 */
function partialText(
  t: (key: string, options?: Record<string, unknown>) => string,
  themes: FamilyTheme[],
  sentThemeIds: number[],
  sentCount: number,
): string {
  const names = sentThemeIds
    .map((id) => themes.find((theme) => theme.id === id))
    .filter((theme): theme is FamilyTheme => theme !== undefined)
    .map((theme) => `「${t(theme.code)}」`)
  if (names.length === 0) return t('requests.sent_partial', { count: sentCount })
  return t('requests.sent_partial_named', { names: names.join('') })
}
