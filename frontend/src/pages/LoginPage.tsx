import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router'
import { messageKeyOf } from '../api/client'
import { logIn } from '../auth/login'
import { homePathFor, useMeState } from '../auth/me'
import { Logo } from '../components/Logo'
import { Message } from '../components/Message'
import { Text } from '../components/Text'
import { usePageTitle } from '../components/usePageTitle'

/**
 * ログインの画面（spec 001 の T097・docs/画面設計.md の UI-C01）。
 * 職員はログイン用の ID、家族はメールアドレスと、パスワードを入れる。
 * ログインすると、ログイン中の人が入れ替わり、下の Navigate で役割ごとの最初の画面へ移る。
 */
export function LoginPage() {
  const state = useMeState()
  const queryClient = useQueryClient()
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  // ブラウザのタブの題：「ログイン ｜ YORIS」（#330）
  usePageTitle('auth.title')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setErrorKey(null)
    setSubmitting(true)
    try {
      await logIn(queryClient, login, password)
    } catch (error) {
      setErrorKey(messageKeyOf(error))
      // 間違えたパスワードを入れたままにしない
      setPassword('')
    } finally {
      setSubmitting(false)
    }
  }

  if (state.status === 'loading') return <Message k="layout.loading" />
  if (state.status === 'error') return <Message k={state.messageKey} />
  if (state.me !== null) {
    // ログインしているのに、開ける画面がない（知らない役割など）
    const home = homePathFor(state.me)
    if (home === '/login') return <Message k="error.forbidden" />
    return <Navigate to={home} replace />
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* 全画面の左上に、ロゴ（デザインの決めごと 12.3。#330）。ログインの前なので、リンクにしない */}
      <header className="p-4">
        <Logo className="h-7" />
      </header>
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center gap-8 px-6 pt-4 pb-12">
        <h1 className="text-center text-2xl font-bold">
          <Text k="auth.title" />
        </h1>
        <form
          onSubmit={submit}
          className="flex flex-col gap-5 rounded-2xl border border-card-line bg-card p-5 shadow-sm min-[600px]:p-6"
        >
          <label className="flex flex-col gap-1">
            {/* span で包む（flex の中で、ふりがなと文字が別の行に割れないように。#192・#196） */}
            <span>
              <Text k="auth.login" />
            </span>
            <input
              id="login"
              name="login"
              required
              autoComplete="username"
              autoCapitalize="none"
              value={login}
              onChange={(event) => setLogin(event.target.value)}
              className="rounded-xl border border-field-line bg-card p-3 text-lg"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span>
              <Text k="auth.password" />
            </span>
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="rounded-xl border border-field-line bg-card p-3 text-lg"
            />
          </label>
          {errorKey && (
            <p role="alert" className="text-red-700">
              <Text k={errorKey} />
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-xl bg-primary p-3 text-lg font-bold text-white disabled:opacity-60"
          >
            <Text k={submitting ? 'auth.submitting' : 'auth.submit'} />
          </button>
        </form>
      </main>
    </div>
  )
}
