import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { canOpen, useMe, type Area } from '../auth/me'
import { Ruby } from '../i18n/Ruby'
import { AreaTabs, type TabItem } from './AreaTabs'
import { Icon } from './Icon'
import { LanguageSwitcher } from './LanguageSwitcher'
import { Logo } from './Logo'
import { LogoutButton } from './LogoutButton'
import { Text } from './Text'

type Props = {
  // 左のロゴと題（1 つのリンク。押すと、そのまとまりのトップへ。同じ行き先のリンクを 2 つに分けない。2.4.4）
  homeTo: string
  titleKey: string
  // もう一方のまとまり（職員の画面 ⇔ 管理画面）。開ける人にだけリンクを出す
  otherArea: Area
  otherTo: string
  otherKey: string
  // 下の段の、行き先のタブ（#437）。名前は、辞書のキー
  tabs: TabItem[]
  tabsLabelKey: string
}

// 丸いボタン（背景か枠があるので、薄い影が付く。デザインの決めごと 7 章）
const PILL = 'min-h-11 rounded-full border border-field-line bg-card text-sm font-semibold'
const PANEL_ID = 'staff-account-panel'

/**
 * 職員の画面・管理画面の上の部分（デザインの決めごと 8 章。#437）。
 * 上の段：ロゴと題・もう一方のまとまりへのリンク・名前のボタン。名前のボタンを押すと、言語とログアウトの段が
 * 上の枠の中に広がる（画面の上に重ねない。職員の画面は、画面を遮る表示を使わない。7 章）。下の段：行き先のタブ。
 * タブレット（617px）でも、上の段は 1 行に収まる。
 */
export function StaffHeader({
  homeTo,
  titleKey,
  otherArea,
  otherTo,
  otherKey,
  tabs,
  tabsLabelKey,
}: Props) {
  const me = useMe().data
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  return (
    <header className="border-b border-card-line bg-card">
      {/* 狭い幅（320px）では右側が次の行に折り返す。左のリンクは縮めない（重なり・横あふれを防ぐ。2.4.11・1.4.10） */}
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-2.5">
        <Link to={homeTo} className="flex shrink-0 items-center gap-3 text-base font-bold">
          <Logo className="h-8" />
          <span className="border-l-2 border-card-line pl-3">
            <Text k={titleKey} />
          </span>
        </Link>
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          {me && canOpen(me, otherArea) && (
            <Link
              to={otherTo}
              className="flex min-h-11 items-center gap-1.5 px-2 font-bold text-primary underline"
            >
              <Icon name="settings" />
              <Text k={otherKey} />
            </Link>
          )}
          {me && (
            <button
              type="button"
              aria-expanded={open}
              aria-controls={PANEL_ID}
              onClick={() => setOpen((value) => !value)}
              className={`${PILL} flex items-center gap-2 py-1 pr-3 pl-1 text-left`}
            >
              {/* 名前の頭の 1 文字の丸（飾り。人物のイラストではなく、文字） */}
              <span
                aria-hidden="true"
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary-soft font-bold text-primary-dark"
              >
                {[...me.display_name][0]}
              </span>
              <span className="leading-tight">
                <span className="block font-bold">{me.display_name}</span>
                {me.role && (
                  <span className="block text-xs text-ink-sub">
                    <Ruby text={t(`role.${me.role}`)} />
                  </span>
                )}
              </span>
              <span className="sr-only">
                <Text k="layout.account_menu" />
              </span>
              <Icon
                name="expand"
                className={`text-xs text-ink-sub transition-transform ${open ? 'rotate-180' : ''}`}
              />
            </button>
          )}
        </div>
      </div>
      {me && (
        <div
          id={PANEL_ID}
          hidden={!open}
          className="flex flex-wrap items-center justify-end gap-3 border-t border-card-line bg-page px-4 py-2.5 text-sm"
        >
          <label htmlFor="staff-language" className="flex items-center gap-2 font-bold">
            <Icon name="language" className="text-primary" />
            <Text k="layout.language_label" />
          </label>
          <LanguageSwitcher id="staff-language" className={`${PILL} px-3`} />
          <LogoutButton
            className={`${PILL} inline-flex items-center gap-1.5 px-4`}
            icon={<Icon name="logout" />}
          />
        </div>
      )}
      <AreaTabs items={tabs} labelKey={tabsLabelKey} />
    </header>
  )
}
