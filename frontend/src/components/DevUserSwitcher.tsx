import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { api, messageKeyOf } from '../api/client'
import { Text } from './Text'

/**
 * 開発用のユーザー切り替え（spec 001 の T013・T019・research.md R-02）。開発のときだけ App.tsx が出す。
 * 画面の右下（家族の下のメニューの上）に出す（上の部分のリンクにかぶらないように）。
 * いまは user_id を入れる。初期データの人の一覧から選べるようにするのは、#62 の次の PR。
 */
export function DevUserSwitcher() {
  const [userId, setUserId] = useState('')
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  async function switchUser(event: FormEvent) {
    event.preventDefault()
    setErrorKey(null)
    try {
      await api.post('/api/dev/switch-user', { user_id: Number(userId) })
    } catch (error) {
      setErrorKey(messageKeyOf(error))
      return
    }
    // 前の人のデータを画面に残さない（読み込んだものを全部捨ててから、最初の画面へ）
    queryClient.clear()
    void navigate('/')
  }

  return (
    <form
      onSubmit={switchUser}
      className="fixed right-2 bottom-20 z-50 max-w-[calc(100vw-1rem)] rounded border border-amber-400 bg-amber-50 p-2 text-xs shadow"
    >
      <p className="font-bold">
        <Text k="dev.switch_user" />
      </p>
      <label className="mr-1 inline-flex items-center">
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
      <button type="submit" className="rounded bg-amber-500 px-2 text-white">
        <Text k="dev.switch" />
      </button>
      {errorKey && (
        <p className="mt-1 text-red-700">
          <Text k={errorKey} />
        </p>
      )}
    </form>
  )
}
