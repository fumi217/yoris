import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { messageKeyOf } from '../api/client'
import { logOut } from '../auth/login'
import { Text } from './Text'

/**
 * ログアウトのボタン（spec 001 の T097）。職員の画面・管理画面の上の部分と、家族の「☰ その他」に置く。
 * ログアウトすると、ログイン中の人が「いない」になり、各画面の守りがログインの画面へ戻す。
 */
export function LogoutButton({ className }: { className?: string }) {
  const queryClient = useQueryClient()
  const [errorKey, setErrorKey] = useState<string | null>(null)

  async function onClick() {
    setErrorKey(null)
    try {
      await logOut(queryClient)
    } catch (error) {
      setErrorKey(messageKeyOf(error))
    }
  }

  return (
    <>
      <button type="button" onClick={onClick} className={className}>
        <Text k="auth.logout" />
      </button>
      {errorKey && (
        <span role="alert" className="text-red-700">
          <Text k={errorKey} />
        </span>
      )}
    </>
  )
}
