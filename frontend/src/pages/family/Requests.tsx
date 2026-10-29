import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import {
  cancelErrorKey,
  sentAtParts,
  statusKeyOf,
  waitingThemeIds,
  type FamilyRequest,
  type FamilyTheme,
} from './requestsView'

const THEMES_KEY = ['family-themes'] as const
const REQUESTS_KEY = ['family-requests'] as const

/** 「知りたいこと」を頼む画面と、送ったリクエストの一覧（UI-F03。001-T060）。 */
export function Requests() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<number | null>(null)
  const [errorKey, setErrorKey] = useState<string | null>(null)

  const themes = useQuery({
    queryKey: THEMES_KEY,
    queryFn: () => api.get<FamilyTheme[]>('/api/family/themes'),
  })
  const requests = useQuery({
    queryKey: REQUESTS_KEY,
    queryFn: () => api.get<FamilyRequest[]>('/api/family/requests'),
  })

  const send = useMutation({
    mutationFn: (themeId: number) => api.post('/api/family/requests', { theme_id: themeId }),
    onSuccess: () => {
      setSelected(null)
      setErrorKey(null)
    },
    onError: (error) => {
      // 選んだテーマが残ると、そのまま「送る」を押し直してしまうので外す
      setSelected(null)
      setErrorKey(messageKeyOf(error))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: REQUESTS_KEY }),
  })

  const cancel = useMutation({
    mutationFn: (requestId: number) => api.delete(`/api/family/requests/${requestId}`),
    onSuccess: () => setErrorKey(null),
    onError: (error) => setErrorKey(cancelErrorKey(error)),
    onSettled: () => queryClient.invalidateQueries({ queryKey: REQUESTS_KEY }),
  })

  if (themes.isPending || requests.isPending) return <Message k="layout.loading" />
  if (themes.isError) return <Message k={messageKeyOf(themes.error)} />
  if (requests.isError) return <Message k={messageKeyOf(requests.error)} />

  const waiting = waitingThemeIds(requests.data)

  return (
    <div className="space-y-6 p-4">
      <section>
        <h2 className="mb-2 font-bold">
          <Text k="requests.choose_title" />
        </h2>
        <ul className="grid grid-cols-2 gap-2">
          {themes.data.map((theme) => {
            const isWaiting = waiting.has(theme.id)
            return (
              <li key={theme.id}>
                <button
                  type="button"
                  disabled={isWaiting}
                  aria-pressed={selected === theme.id}
                  onClick={() => setSelected(theme.id)}
                  className={`flex w-full flex-col items-center gap-1 rounded border p-3 text-sm ${
                    selected === theme.id ? 'border-sky-600 bg-sky-50 font-bold' : ''
                  } ${isWaiting ? 'bg-gray-100 text-gray-400' : ''}`}
                >
                  <span aria-hidden="true">{theme.emoji}</span>
                  {/* 縦に並べる枠の中で、ふりがなと文字が別々の行にならないよう、1 つにまとめる */}
                  <span>
                    <Text k={theme.code} />
                  </span>
                  {isWaiting && (
                    <span className="text-xs">
                      <Text k="requests.status_waiting_short" />
                    </span>
                  )}
                </button>
              </li>
            )
          })}
        </ul>
        <button
          type="button"
          disabled={selected === null || send.isPending}
          onClick={() => selected !== null && send.mutate(selected)}
          className="mt-3 w-full rounded bg-sky-700 p-3 font-bold text-white disabled:opacity-60"
        >
          <Text k="requests.send" />
        </button>
        {errorKey && (
          <p role="alert" className="mt-2 text-red-700">
            <Text k={errorKey} />
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-2 font-bold">
          <Text k="requests.list_title" />
        </h2>
        {requests.data.length === 0 ? (
          <p className="text-gray-600">
            <Text k="requests.empty" />
          </p>
        ) : (
          <ul className="space-y-2">
            {requests.data.map((request) => (
              <li key={request.id} className="rounded border p-3">
                <div className="flex items-center gap-2">
                  <span aria-hidden="true">{request.emoji}</span>
                  <span className="font-bold">
                    <Text k={request.theme_code} />
                  </span>
                </div>
                <p className="text-sm">
                  <Text k={statusKeyOf(request)} />
                </p>
                <p className="text-sm text-gray-600">
                  <Ruby text={t('requests.sent_at', sentAtParts(request.created_at))} />（
                  <Ruby
                    text={
                      request.days_ago === 0
                        ? t('requests.days_ago_zero')
                        : t('requests.days_ago', { count: request.days_ago })
                    }
                  />
                  ）
                </p>
                {request.status === 'waiting' && request.overdue && (
                  <p className="mt-1 text-sm text-red-700">
                    <Text k="requests.overdue" />
                  </p>
                )}
                {request.status === 'waiting' && (
                  <button
                    type="button"
                    disabled={cancel.isPending}
                    onClick={() => cancel.mutate(request.id)}
                    className="mt-2 rounded border px-3 py-1 text-sm"
                  >
                    <Text k="requests.cancel" />
                  </button>
                )}
                {request.status === 'answered' && (
                  <Link to="/family" className="mt-2 inline-block text-sm text-sky-700 underline">
                    <Text k="requests.see_reply" />
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
