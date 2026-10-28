import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { Text } from '../../components/Text'
import { stripRuby } from '../../i18n/rubyText'
import {
  nameProblem,
  OCCUPATIONS,
  ROLES,
  toBody,
  type CreatedStaff,
  type StaffCreateBody,
  type StaffRoleCode,
} from './staffAccountRules'

/**
 * 職員のアカウントを作る（001-T088。生活相談員・施設長。守りは API の 403）。
 * 表示名・役割・職種を入れて「作る」と、ログイン用の ID と初期パスワードが 1 回だけ出る。
 * パスワードは作った直後の返事でだけ返ってくる（あとから見られない）。画面を閉じる・離れると消える。
 */
export function StaffAccounts() {
  const create = useMutation({
    mutationFn: (body: StaffCreateBody) => api.post<CreatedStaff>('/api/admin/staff', body),
    // 初期パスワードを、画面を閉じたあともメモリに残さない（reset() ですぐ消える）
    gcTime: 0,
  })

  return (
    <section className="space-y-6 p-4">
      <h1 className="text-xl font-bold">
        <Text k="staff_accounts.title" />
      </h1>
      {create.isSuccess ? (
        // 閉じると、フォームの入力も空に戻る（次の職員を続けて作れる）
        <CreatedView created={create.data} onClose={() => create.reset()} />
      ) : (
        <StaffFormView
          saving={create.isPending}
          errorKey={create.isError ? messageKeyOf(create.error) : null}
          onSubmit={(body) => create.mutate(body)}
        />
      )}
    </section>
  )
}

/** 項目名の横の「※必須」（申し込みの画面と同じ赤い文字）。 */
function Required() {
  return (
    <span className="text-sm font-normal text-red-700">
      <Text k="staff_accounts.required" />
    </span>
  )
}

type FormProps = {
  saving: boolean
  errorKey: string | null
  onSubmit: (body: StaffCreateBody) => void
}

/** 入力のフォーム（テストではこれを直接出す）。 */
export function StaffFormView({ saving, errorKey, onSubmit }: FormProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [role, setRole] = useState<StaffRoleCode>('care_worker')
  const [occupation, setOccupation] = useState('')
  // 押す前から赤い文字を出さない
  const [tried, setTried] = useState(false)
  const problem = nameProblem(name)

  return (
    <form
      className="space-y-5"
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        setTried(true)
        if (problem === null && !saving) onSubmit(toBody(name, role, occupation))
      }}
    >
      {/* 申し込みの画面と同じ、先頭の案内（入力して押す → 押すと表示される） */}
      <p className="text-sm leading-relaxed text-gray-600">
        <Text k="staff_accounts.note" />
      </p>

      <div className="space-y-2">
        <label htmlFor="staff-display-name" className="flex items-baseline gap-2 font-bold">
          <span>
            <Text k="staff_accounts.display_name" />
          </span>
          <Required />
        </label>
        <p id="staff-display-name-hint" className="text-sm leading-relaxed text-gray-600">
          <Text k="staff_accounts.display_name_hint" />
        </p>
        <input
          id="staff-display-name"
          type="text"
          value={name}
          autoComplete="off"
          aria-describedby="staff-display-name-hint"
          aria-required="true"
          aria-invalid={tried && problem !== null}
          onChange={(event) => setName(event.target.value)}
          className="w-full rounded border-2 border-gray-300 p-3"
        />
        {tried && problem !== null && (
          <p role="alert" className="text-red-700">
            <Text k={`staff_accounts.name_${problem}`} />
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="staff-role" className="flex items-baseline gap-2 font-bold">
          <span>
            <Text k="staff_accounts.role" />
          </span>
          <Required />
        </label>
        <p id="staff-role-hint" className="text-sm leading-relaxed text-gray-600">
          <Text k="staff_accounts.role_hint" />
          {/* TODO: 役割の説明の行き先が決まったら、href を入れる（今は何も開かない） */}
          <a
            href="#"
            onClick={(event) => event.preventDefault()}
            className="text-sky-700 underline"
          >
            <Text k="staff_accounts.role_hint_link" />
          </a>
          <Text k="staff_accounts.role_hint_after" />
        </p>
        <select
          id="staff-role"
          value={role}
          aria-describedby="staff-role-hint"
          aria-required="true"
          onChange={(event) => setRole(event.target.value as StaffRoleCode)}
          className="w-full rounded border-2 border-gray-300 bg-white p-3"
        >
          {/* 役割の名前は、職種の辞書（occupation.*）と同じ（役割の 5 つは職種の候補にも入っている） */}
          {ROLES.map((code) => (
            <option key={code} value={code}>
              {stripRuby(t(`occupation.${code}`))}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label htmlFor="staff-occupation" className="flex items-baseline gap-2 font-bold">
          <span>
            <Text k="staff_accounts.occupation" />
          </span>
          <span className="text-sm font-normal text-gray-600">
            <Text k="staff_accounts.optional" />
          </span>
        </label>
        <p id="staff-occupation-hint" className="text-sm leading-relaxed text-gray-600">
          <Text k="staff_accounts.occupation_hint" />
        </p>
        <select
          id="staff-occupation"
          value={occupation}
          aria-describedby="staff-occupation-hint"
          onChange={(event) => setOccupation(event.target.value)}
          className="w-full rounded border-2 border-gray-300 bg-white p-3"
        >
          <option value="">{stripRuby(t('staff_accounts.occupation_none'))}</option>
          {OCCUPATIONS.map((code) => (
            <option key={code} value={code}>
              {stripRuby(t(`occupation.${code}`))}
            </option>
          ))}
        </select>
      </div>

      <p role="status" aria-live="polite" className="min-h-6 text-sm">
        {errorKey && (
          <span className="text-red-700">
            <Text k={errorKey} />
          </span>
        )}
      </p>
      <button
        type="submit"
        disabled={saving}
        className="w-full rounded bg-sky-700 p-3 font-bold text-white disabled:opacity-50 sm:w-auto sm:px-8"
      >
        <Text k={saving ? 'staff_accounts.submitting' : 'staff_accounts.submit'} />
      </button>
    </form>
  )
}

type CreatedProps = {
  created: CreatedStaff
  onClose: () => void
}

/** 作ったあとの表示（ID と初期パスワード。テストではこれを直接出す）。 */
export function CreatedView({ created, onClose }: CreatedProps) {
  const { t } = useTranslation()
  const [copyState, setCopyState] = useState<'idle' | 'done' | 'failed'>('idle')

  async function copy() {
    try {
      await navigator.clipboard.writeText(
        `${t('staff_accounts.login_id')}: ${created.login_id}\n${stripRuby(t('staff_accounts.initial_password'))}: ${created.initial_password}`,
      )
      setCopyState('done')
    } catch {
      // 古い環境などでは、クリップボードに書けない。文字を選んでコピーしてもらう
      setCopyState('failed')
    }
  }

  return (
    <div className="space-y-5">
      <p role="status" className="font-bold text-green-800">
        <Text k="staff_accounts.created_title" />
      </p>
      <dl className="space-y-3 rounded border-2 border-gray-300 p-4">
        <div>
          <dt className="text-sm text-gray-600">
            <Text k="staff_accounts.display_name" />
          </dt>
          <dd className="text-lg">{created.display_name}</dd>
        </div>
        <div>
          <dt className="text-sm text-gray-600">
            <Text k="staff_accounts.login_id" />
          </dt>
          <dd className="select-all font-mono text-2xl">{created.login_id}</dd>
        </div>
        <div>
          <dt className="text-sm text-gray-600">
            <Text k="staff_accounts.initial_password" />
          </dt>
          <dd className="select-all font-mono text-2xl">{created.initial_password}</dd>
        </div>
      </dl>
      <p role="alert" className="text-red-700">
        <Text k="staff_accounts.created_note" />
      </p>
      <p role="status" aria-live="polite" className="min-h-6 text-sm">
        {/* コピーできたことは、ボタン自体が変わって伝える。読み上げには、見えない文で伝える */}
        {copyState === 'done' && (
          <span className="sr-only">
            <Text k="staff_accounts.copied" />
          </span>
        )}
        {copyState === 'failed' && (
          <span className="text-red-700">
            <Text k="staff_accounts.copy_failed" />
          </span>
        )}
      </p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void copy()}
          // 申し込みの完了画面と同じ：押したあとは、ボタン自体が緑の「✓ コピーしました」に変わる
          className={`rounded border-2 p-3 font-bold transition active:scale-95 ${
            copyState === 'done'
              ? 'border-green-700 bg-green-50 text-green-800'
              : 'border-sky-700 text-sky-700 hover:bg-sky-50 active:bg-sky-100'
          }`}
        >
          <Text k={copyState === 'done' ? 'staff_accounts.copied' : 'staff_accounts.copy'} />
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded bg-sky-700 p-3 font-bold text-white"
        >
          <Text k="staff_accounts.close" />
        </button>
      </div>
    </div>
  )
}
