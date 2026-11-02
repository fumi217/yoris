import { useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { messageKeyOf } from '../api/client'
import { logOut } from '../auth/login'
import { Text } from './Text'

/**
 * ログアウトのボタン（spec 001 の T097）。職員の画面・管理画面の上の部分と、家族の「その他」に置く。
 * ログアウトすると、ログイン中の人が「いない」になり、各画面の守りがログインの画面へ戻す。
 */
export function LogoutButton({ className, icon }: { className?: string; icon?: ReactNode }) {
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
        {icon}
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
