import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router'
import { api, messageKeyOf } from '../api/client'
import { stripRuby } from '../i18n/rubyText'
import { isFamilyPath, useDevHidden } from './devMode'
import { DEV_USERS_QUERY_KEY, switchDevUser } from './devSwitch'
import { devUserLabel, type DevUser } from './devUsers'
import { Icon } from './Icon'
import { Text } from './Text'

/**
 * 開発用のユーザー切り替え（spec 001 の T013・T019・research.md R-02・#428）。開発のときだけ App.tsx が出す。
 * ふだんは出す。URL の `?dev=0` で隠し（デモの録画など）、`?dev=1` で出し直す（devMode.ts）。
 * 幅 1280px 未満は、左下の小さなアイコンに畳み、押すとその上にシートが開く。
 * 家族の画面は、下のメニューの上に置く（右寄せのキャラクター（#339）には重ならない）。
 * 幅 1280px 以上は、アイコンにせず、今までのパネルを右下に出す。
 * 初期データ（`python -m app.seed`）の人の一覧から選ぶ。
 */
type ShellProps = {
  open: boolean
  inFamily: boolean
  onToggle: () => void
  onSubmit: (event: FormEvent) => void
  children: ReactNode
}

/** アイコンとシートの枠（開閉と置き場所だけ。中身は children） */
export function DevSwitcherShell({ open, inFamily, onToggle, onSubmit, children }: ShellProps) {
  const { t } = useTranslation()
  return (
    <div
      // 家族の画面は下のメニューの上、ほかは画面の下から少し上。幅が広いときは、右下に今までの高さで出す
      className={`fixed left-2 z-50 flex max-w-[calc(100vw-1rem)] flex-col items-start gap-2 xl:right-2 xl:left-auto xl:bottom-[calc(var(--family-menu-height)+5.5rem)] ${
        inFamily ? 'bottom-[calc(var(--family-menu-height)+1rem)]' : 'bottom-4'
      }`}
    >
      <form
        onSubmit={onSubmit}
        className={`max-w-full rounded border border-amber-400 bg-amber-50 p-2 text-xs shadow xl:block ${
          open ? 'block' : 'hidden'
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <p className="font-bold">
            <Text k="dev.switch_user" />
          </p>
          <button
            type="button"
            onClick={onToggle}
            aria-label={stripRuby(t('dev.close'))}
            className="xl:hidden"
          >
            <Icon name="close" />
          </button>
        </div>
        {children}
      </form>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-label={stripRuby(t(open ? 'dev.close' : 'dev.open'))}
        className="flex size-10 items-center justify-center rounded-full border border-amber-400 bg-amber-50 text-amber-700 shadow xl:hidden"
      >
        <Icon name="dev-switch" className="text-lg" />
      </button>
    </div>
  )
}

export function DevUserSwitcher() {
  const hidden = useDevHidden()
  // 隠すときは、人の一覧も読み込まない
  return hidden ? null : <DevSwitcher />
}

function DevSwitcher() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [userId, setUserId] = useState('')
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const users = useQuery({
    queryKey: DEV_USERS_QUERY_KEY,
    queryFn: () => api.get<DevUser[]>('/api/dev/users'),
    // 開発のときだけの API。読めないときは試し直さず、すぐに知らせる
    retry: false,
  })

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setErrorKey(null)
    setErrorKey(
      await switchDevUser(Number(userId), { queryClient, navigate, close: () => setOpen(false) }),
    )
  }

  const staff = users.data?.filter((user) => user.kind === 'staff') ?? []
  const families = users.data?.filter((user) => user.kind === 'family') ?? []
  const shownErrorKey = errorKey ?? (users.isError ? messageKeyOf(users.error) : null)

  return (
    <DevSwitcherShell
      open={open}
      inFamily={isFamilyPath(pathname)}
      onToggle={() => setOpen((value) => !value)}
      onSubmit={onSubmit}
    >
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
              className="ml-1 w-16 rounded border border-field-line px-1"
            />
          </label>
        ) : (
          <select
            required
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            aria-label={stripRuby(t('dev.switch_user'))}
            className="max-w-48 rounded border border-field-line px-1"
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
    </DevSwitcherShell>
  )
}
