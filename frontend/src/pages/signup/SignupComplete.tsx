import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { StepNavigation } from '../../components/StepNavigation'
import { Text } from '../../components/Text'
import { SIGNUP_STEPS } from './steps'
import { clearIdempotencyKey } from './idempotencyKey'

type CompleteResult = {
  status: 'confirming' | 'completed' | 'not_completed'
  login_id?: string
}

// アカウントができたかを聞き直す間隔（ミリ秒）。Webhook が届くまでの数秒だけ待つ
const POLL_INTERVAL_MS = 3000
// 読み直しを続ける長さ（ミリ秒）。Webhook が届かないとき、開いている間ずっと読み直さないように、
// 2 分たったら止めて、少し待ってから読み直すよう案内する
const POLL_LIMIT_MS = 2 * 60 * 1000

/**
 * 申し込み完了の画面（`/signup/complete?session_id=`。Stripe から戻る先。spec 002 の T025・US1 のシナリオ 2・4）。
 * アカウントは Stripe からの知らせ（Webhook）で作るので、戻ってきた時点ではまだないことがある。
 * 3 秒ごとに読み直し（最長 2 分）、できたらログイン用の ID を出す。
 */
export function SignupComplete() {
  const [params] = useSearchParams()
  const sessionId = params.get('session_id')
  const [startedAt] = useState(() => Date.now())
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setTimedOut(true), POLL_LIMIT_MS)
    return () => clearTimeout(timer)
  }, [])

  const result = useQuery({
    queryKey: ['billing', 'complete', sessionId],
    queryFn: () =>
      api.get<CompleteResult>(
        `/api/billing/signup/complete?session_id=${encodeURIComponent(sessionId ?? '')}`,
      ),
    enabled: sessionId !== null,
    // タブを戻したときに読み直さない（ID は作ってから 1 時間までしか返らないので、
    // 出した ID が読み直しで消えないように）
    refetchOnWindowFocus: false,
    // できるまで（confirming の間）だけ、上限の時間まで読み直す
    refetchInterval: (query) =>
      query.state.data?.status === 'confirming' && Date.now() - startedAt < POLL_LIMIT_MS
        ? POLL_INTERVAL_MS
        : false,
  })

  // 申し込みが終わったので、二度押し対策の値を消す
  const status = result.data?.status
  useEffect(() => {
    if (status === 'completed') clearIdempotencyKey()
  }, [status])

  if (sessionId === null) return <CompleteView status="not_completed" />
  // 取れた結果があれば出し続ける（読み直しが 1 回失敗しても、確認中の表示を消さない）
  if (result.data)
    return (
      <CompleteView
        status={result.data.status}
        loginId={result.data.login_id}
        timedOut={timedOut}
      />
    )
  if (result.isError) return <Message k={messageKeyOf(result.error)} />
  return <Message k="layout.loading" />
}

/** 画面の中身（テストではこれを直接出す）。 */
export function CompleteView({
  status,
  loginId,
  timedOut = false,
}: {
  status: CompleteResult['status']
  loginId?: string
  timedOut?: boolean
}) {
  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      {/* 確認中・確認できなかったときは「お支払い」、できたら「完了」にいる */}
      <StepNavigation
        labelKey="steps.label"
        steps={SIGNUP_STEPS}
        current={status === 'completed' ? 3 : 2}
        errorStep={status === 'not_completed' ? 2 : undefined}
      />
      {status === 'confirming' && (
        <p role="status" aria-live="polite">
          <Text k={timedOut ? 'signup_complete.slow' : 'signup_complete.confirming'} />
        </p>
      )}

      {status === 'completed' && (
        <>
          <h1 className="text-2xl font-bold">
            <Text k="signup_complete.done_title" />
          </h1>
          {loginId ? (
            <div className="space-y-2 rounded border-2 border-sky-700 p-4">
              <p className="text-sm">
                <Text k="signup_complete.login_id" />
              </p>
              <p className="text-3xl font-bold tracking-wider" data-testid="login-id">
                {loginId}
              </p>
              <p className="font-bold text-red-700">
                <Text k="signup_complete.keep" />
              </p>
            </div>
          ) : (
            <p>
              <Text k="signup_complete.id_expired" />
            </p>
          )}
          <Link
            to="/login"
            className="block rounded bg-sky-700 p-3 text-center text-lg font-bold text-white"
          >
            <Text k="signup_complete.to_login" />
          </Link>
        </>
      )}

      {status === 'not_completed' && (
        <>
          <p role="alert">
            <Text k="signup_complete.not_completed" />
          </p>
          <Link to="/signup" className="block rounded border p-3 text-center text-lg">
            <Text k="signup_complete.retry" />
          </Link>
        </>
      )}
    </main>
  )
}
