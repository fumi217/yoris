import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Logo } from '../../components/Logo'
import { Message } from '../../components/Message'
import { StepNavigation } from '../../components/StepNavigation'
import { Text } from '../../components/Text'
import { usePageTitle } from '../../components/usePageTitle'
import {
  FIELD_ORDER,
  placeServerError,
  validateSignup,
  type FieldErrors,
  type FieldName,
} from './fieldErrors'
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
  // ブラウザのタブの題：「お申し込み ｜ YORIS」（#330）
  usePageTitle('signup.title')
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
        facility_name: values.facility_name.trim(),
        director_name: values.director_name.trim(),
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
  // 送る前の確認で見つけた間違い（全部の欄をまとめて確かめて、欄ごとに辞書の文で伝える）
  const [localErrors, setLocalErrors] = useState<FieldErrors>({})
  // カーソルを移す先。ボタンを押したときに決める（同じ欄でも、押すたびに移すため id を変える）
  const [focusRequest, setFocusRequest] = useState<{ field: FieldName; id: number } | null>(null)

  // 文字を直した欄は、その欄のエラーを消す
  const set = (name: FieldName) => (value: string) => {
    setValues((current) => ({ ...current, [name]: value }))
    setLocalErrors((current) => {
      if (!(name in current)) return current
      const rest = { ...current }
      delete rest[name]
      return rest
    })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const errors = validateSignup(values)
    setLocalErrors(errors)
    // 間違いのある欄のうち、いちばん上にカーソルを移す
    const first = FIELD_ORDER.find((name) => errors[name])
    if (first) {
      setFocusRequest((current) => ({ field: first, id: (current?.id ?? 0) + 1 }))
      return
    }
    onSubmit(values)
  }

  // エラーは、その欄のすぐ下に出す。欄が決まらないものだけ、ボタンの上に出す
  const server = errorKey ? placeServerError(errorKey) : null
  const hasLocalErrors = Object.keys(localErrors).length > 0
  const fieldErrors: FieldErrors = hasLocalErrors
    ? localErrors
    : server?.field
      ? { [server.field]: server.key }
      : {}
  const formErrorKey = !hasLocalErrors && server && !server.field ? server.key : null

  // カーソルは「ボタンを押したあと」だけ移す。「間違いのある欄が変わったとき」にすると、
  // 文字を直してエラーが消えたとたんに、次の間違いの欄へカーソルが勝手に移ってしまう
  useEffect(() => {
    if (focusRequest) document.getElementById(focusRequest.field)?.focus()
  }, [focusRequest])
  // サーバーに断られたときは、その欄に移す
  useEffect(() => {
    const field = errorKey ? placeServerError(errorKey).field : null
    if (field) document.getElementById(field)?.focus()
  }, [errorKey])

  return (
    <>
      {/* 全画面の左上に、ロゴ（デザインの決めごと 12.3。#330）。ログインの前なので、リンクにしない */}
      <header className="p-4">
        <Logo className="h-7" />
      </header>
      <main className="mx-auto max-w-md space-y-6 p-6">
        <StepNavigation labelKey="steps.label" steps={SIGNUP_STEPS} current={1} />
        <div>
          <h1 className="text-2xl font-bold">
            <Text k="signup.title" />
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            <Text k="signup.lead" />
          </p>
          <p className="mt-3 rounded-lg border border-card-line bg-card p-3">
            {plan.plan_name}{' '}
            <span className="font-bold">{plan.amount_jpy.toLocaleString('ja-JP')}</span>
            <Text k="signup.per_month" />
          </p>
        </div>

        {canceled && (
          <p role="status" className="rounded border border-orange-300 bg-orange-50 p-3">
            <Text k="signup.canceled" />
          </p>
        )}

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <Field
            name="facility_name"
            labelKey="signup.facility_name"
            value={values.facility_name}
            onChange={set('facility_name')}
            autoComplete="organization"
            errorKey={fieldErrors.facility_name}
          />
          <Field
            name="director_name"
            labelKey="signup.director_name"
            hintKey="signup.director_name_hint"
            value={values.director_name}
            onChange={set('director_name')}
            autoComplete="name"
            errorKey={fieldErrors.director_name}
          />
          <Field
            name="email"
            type="email"
            labelKey="signup.email"
            value={values.email}
            onChange={set('email')}
            autoComplete="email"
            errorKey={fieldErrors.email}
          />
          <Field
            name="email_confirm"
            type="email"
            labelKey="signup.email_confirm"
            value={values.email_confirm}
            onChange={set('email_confirm')}
            autoComplete="off"
            errorKey={fieldErrors.email_confirm}
          />
          <Field
            name="password"
            type="password"
            labelKey="signup.password"
            hintKey="signup.password_hint"
            value={values.password}
            onChange={set('password')}
            autoComplete="new-password"
            errorKey={fieldErrors.password}
          />

          {formErrorKey && (
            <p role="alert" className="text-red-700">
              <Text k={formErrorKey} />
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-primary p-3 text-lg font-bold text-white disabled:opacity-60"
          >
            <Text k={submitting ? 'signup.submitting' : 'signup.submit'} />
          </button>
        </form>
      </main>
    </>
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
  // この欄のエラー（辞書のキー）。あれば、欄を赤い枠にして、すぐ下に出す
  errorKey?: string
}

function Field({
  name,
  labelKey,
  hintKey,
  type = 'text',
  value,
  onChange,
  errorKey,
  ...rest
}: FieldProps) {
  const errorId = `${name}-error`
  const hintId = `${name}-hint`
  return (
    <label className="flex flex-col gap-1">
      {/* デジタル庁の入力欄の並び：項目名（横に「※必須」）→ ヒント → 入力欄 → エラー */}
      {/* span で包む（flex の中で、ふりがなと文字が別の行に割れないように） */}
      <span className="flex items-baseline gap-2">
        <span>
          <Text k={labelKey} />
        </span>
        <span className="text-sm text-red-700">
          <Text k="signup.required" />
        </span>
      </span>
      {hintKey && (
        <span id={hintId} className="text-sm text-gray-600">
          <Text k={hintKey} />
        </span>
      )}
      <input
        id={name}
        name={name}
        type={type}
        required
        aria-invalid={errorKey ? true : undefined}
        aria-describedby={
          [errorKey && errorId, hintKey && hintId].filter(Boolean).join(' ') || undefined
        }
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`rounded p-3 text-lg ${errorKey ? 'border-2 border-red-700 bg-red-50' : 'border border-field-line'}`}
        {...rest}
      />
      {errorKey && (
        // 文頭は全角の「＊」（デジタル庁のエラーテキストの決まり）
        <span id={errorId} role="alert" className="text-sm font-bold text-red-700">
          ＊<Text k={errorKey} />
        </span>
      )}
    </label>
  )
}
