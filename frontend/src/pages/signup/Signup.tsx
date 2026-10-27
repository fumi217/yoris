import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { StepNavigation } from '../../components/StepNavigation'
import { Text } from '../../components/Text'
import { SIGNUP_STEPS } from './steps'
import { clearIdempotencyKey, getIdempotencyKey } from './idempotencyKey'

type Plan = { plan_name: string; amount_jpy: number }
type SignupValues = {
  facility_name: string
  director_name: string
  email: string
  email_confirm: string
  password: string
}

/**
 * 申し込みページ（`/signup`。ログインなし。spec 002 の T024・US1 のシナリオ 1・3・5）。
 * 施設名・施設長の名前・メールアドレス（2 回）・パスワードを入れて、Stripe の支払い画面へ移る。
 * 支払い画面から「戻る」で戻ったとき（`?canceled=1&key=`）は、申し込みを取り消して、新しい値で申し込み直せる。
 * 施設がすでにあるときは、API が 404 を返すので「見つかりませんでした」と出す（理由は出さない。FR-016）。
 */
export function Signup() {
  const [params] = useSearchParams()
  const canceled = params.get('canceled') === '1'
  const [cancelDone, setCancelDone] = useState(!canceled)

  const plan = useQuery({
    queryKey: ['billing', 'plan'],
    queryFn: () => api.get<Plan>('/api/billing/signup'),
    // 施設がある（404）を試し直さない
    retry: false,
  })

  // 「戻る」で戻ったとき：その申し込みを取り消して、値を作り直す。終わるまで申し込めないようにする
  const key = params.get('key')
  useEffect(() => {
    if (!canceled) return
    let ignore = false
    const cancelKey = key ?? getIdempotencyKey()
    api
      .post('/api/billing/signup/cancel', { idempotency_key: cancelKey })
      .catch(() => {})
      .finally(() => {
        // 取り消した申し込みの値だけを消す（別のタブの新しい申し込みの値は消さない）
        clearIdempotencyKey(cancelKey)
        if (!ignore) setCancelDone(true)
      })
    return () => {
      ignore = true
    }
  }, [canceled, key])

  const submit = useMutation({
    mutationFn: (values: SignupValues) =>
      api.post<{ checkout_url: string }>('/api/billing/signup', {
        idempotency_key: getIdempotencyKey(),
        ...values,
        email: values.email.trim(),
        email_confirm: values.email_confirm.trim(),
      }),
    onSuccess: ({ checkout_url }) => {
      // 支払い画面は https の Stripe の画面だけ。それ以外の URL へは移らない
      if (new URL(checkout_url, window.location.href).protocol !== 'https:') {
        throw new Error('invalid checkout url')
      }
      window.location.assign(checkout_url)
    },
  })

  if (plan.isPending) return <Message k="layout.loading" />
  if (plan.isError) return <Message k={messageKeyOf(plan.error)} />
  return (
    <SignupForm
      plan={plan.data}
      canceled={canceled}
      // 移動中も、押せないままにする
      submitting={submit.isPending || submit.isSuccess || !cancelDone}
      errorKey={submit.isError ? messageKeyOf(submit.error) : null}
      onSubmit={(values) => submit.mutate(values)}
    />
  )
}

type FormProps = {
  plan: Plan
  canceled: boolean
  submitting: boolean
  errorKey: string | null
  onSubmit: (values: SignupValues) => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function SignupForm({ plan, canceled, submitting, errorKey, onSubmit }: FormProps) {
  const [values, setValues] = useState<SignupValues>({
    facility_name: '',
    director_name: '',
    email: '',
    email_confirm: '',
    password: '',
  })
  const set = (name: keyof SignupValues) => (value: string) =>
    setValues((current) => ({ ...current, [name]: value }))

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    onSubmit(values)
  }

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <StepNavigation labelKey="steps.label" steps={SIGNUP_STEPS} current={1} />
      <div>
        <h1 className="text-2xl font-bold">
          <Text k="signup.title" />
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          <Text k="signup.lead" />
        </p>
        <p className="mt-3 rounded bg-sky-50 p-3">
          {plan.plan_name}{' '}
          <span className="font-bold">{plan.amount_jpy.toLocaleString('ja-JP')}</span>{' '}
          <Text k="signup.per_month" />
        </p>
      </div>

      {canceled && (
        <p role="status" className="rounded border border-orange-300 bg-orange-50 p-3">
          <Text k="signup.canceled" />
        </p>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Field
          name="facility_name"
          labelKey="signup.facility_name"
          value={values.facility_name}
          onChange={set('facility_name')}
          autoComplete="organization"
        />
        <Field
          name="director_name"
          labelKey="signup.director_name"
          value={values.director_name}
          onChange={set('director_name')}
          autoComplete="name"
        />
        <Field
          name="email"
          type="email"
          labelKey="signup.email"
          value={values.email}
          onChange={set('email')}
          autoComplete="email"
        />
        <Field
          name="email_confirm"
          type="email"
          labelKey="signup.email_confirm"
          value={values.email_confirm}
          onChange={set('email_confirm')}
          autoComplete="off"
        />
        <Field
          name="password"
          type="password"
          labelKey="signup.password"
          hintKey="signup.password_hint"
          value={values.password}
          onChange={set('password')}
          autoComplete="new-password"
          // 半角の英数字と記号（空白を含む）で 8〜64 文字（サーバーの決まり。最後の確認はサーバー）
          pattern="[ -~]{8,64}"
        />

        <p className="text-sm text-gray-600">
          <Text k="signup.payment_note" />
        </p>
        {errorKey && (
          <p role="alert" className="text-red-700">
            <Text k={errorKey} />
          </p>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-sky-700 p-3 text-lg font-bold text-white disabled:opacity-60"
        >
          <Text k={submitting ? 'signup.submitting' : 'signup.submit'} />
        </button>
      </form>
    </main>
  )
}

type FieldProps = {
  name: string
  labelKey: string
  hintKey?: string
  type?: string
  value: string
  onChange: (value: string) => void
  autoComplete: string
  pattern?: string
}

function Field({ name, labelKey, hintKey, type = 'text', value, onChange, ...rest }: FieldProps) {
  return (
    <label className="flex flex-col gap-1">
      {/* span で包む（flex の中で、ふりがなと文字が別の行に割れないように） */}
      <span>
        <Text k={labelKey} />
      </span>
      <input
        id={name}
        name={name}
        type={type}
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded border p-3 text-lg"
        {...rest}
      />
      {hintKey && (
        <span className="text-sm text-gray-600">
          <Text k={hintKey} />
        </span>
      )}
    </label>
  )
}
