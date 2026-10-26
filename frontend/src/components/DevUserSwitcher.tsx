import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import { api, messageKeyOf } from '../api/client'
import { stripRuby } from '../i18n/rubyText'
import { devUserLabel, type DevUser } from './devUsers'
import { Text } from './Text'

/**
 * 開発用のユーザー切り替え（spec 001 の T013・T019・research.md R-02）。開発のときだけ App.tsx が出す。
 * 画面の右下（家族の下のメニューの上）に出す（上の部分のリンクにかぶらないように）。
 * 初期データ（`python -m app.seed`）の人の一覧から選ぶ。
 */
const DEV_USERS_QUERY_KEY = ['dev', 'users'] as const

export function DevUserSwitcher() {
  const { t } = useTranslation()
  const [userId, setUserId] = useState('')
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const users = useQuery({
    queryKey: DEV_USERS_QUERY_KEY,
    queryFn: () => api.get<DevUser[]>('/api/dev/users'),
    // 開発のときだけの API。読めないときは試し直さず、すぐに知らせる
    retry: false,
  })

  async function switchUser(event: FormEvent) {
    event.preventDefault()
    setErrorKey(null)
    try {
      await api.post('/api/dev/switch-user', { user_id: Number(userId) })
    } catch (error) {
      setErrorKey(messageKeyOf(error))
      return
    }
    // 前の人のデータを画面に残さない（読み込んだものを捨ててから、最初の画面へ）。
    // 人の一覧は、だれがログインしていても同じなので残す
    queryClient.removeQueries({
      predicate: (query) => query.queryKey[0] !== DEV_USERS_QUERY_KEY[0],
    })
    void navigate('/')
  }

  const staff = users.data?.filter((user) => user.kind === 'staff') ?? []
  const families = users.data?.filter((user) => user.kind === 'family') ?? []
  const shownErrorKey = errorKey ?? (users.isError ? messageKeyOf(users.error) : null)

  return (
    <form
      onSubmit={switchUser}
      className="fixed right-2 bottom-20 z-50 max-w-[calc(100vw-1rem)] rounded border border-amber-400 bg-amber-50 p-2 text-xs shadow"
    >
      <p className="font-bold">
        <Text k="dev.switch_user" />
      </p>
      <div className="flex items-center gap-1">
        {users.isError ? (
          // 一覧が読めないときは、user_id を直接入れて切り替える
          <label className="inline-flex items-center">
            <Text k="dev.user_id" />
            <input
              type="number"
              min={1}
              required
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              className="ml-1 w-16 rounded border px-1"
            />
          </label>
        ) : (
          <select
            required
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            aria-label={stripRuby(t('dev.switch_user'))}
            className="max-w-48 rounded border px-1"
          >
            <option value="">
              {stripRuby(t(users.isPending ? 'layout.loading' : 'dev.choose'))}
            </option>
            {users.data && (
              <>
                <optgroup label={stripRuby(t('dev.staff'))}>
                  {staff.map((user) => (
                    <option key={user.user_id} value={user.user_id}>
                      {devUserLabel(user, t)}
                    </option>
                  ))}
                </optgroup>
                <optgroup label={stripRuby(t('dev.family'))}>
                  {families.map((user) => (
                    <option key={user.user_id} value={user.user_id}>
                      {devUserLabel(user, t)}
                    </option>
                  ))}
                </optgroup>
              </>
            )}
          </select>
        )}
        <button type="submit" className="rounded bg-amber-500 px-2 text-white">
          <Text k="dev.switch" />
        </button>
      </div>
      {shownErrorKey && (
        <p className="mt-1 text-red-700">
          <Text k={shownErrorKey} />
        </p>
      )}
    </form>
  )
}
