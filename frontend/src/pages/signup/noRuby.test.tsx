// 申し込みのフェーズ（操作するのは施設長）は、ふりがななしと決めた（spec 002 の Assumptions）。
// 辞書に `{漢字|かんじ}` を足してしまうと、ふりがなが出てしまうので、ここで気づけるようにする。
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import ja from '../../i18n/ja.json'
import { StepNavigation } from '../../components/StepNavigation'
import { CompleteView } from './SignupComplete'
import { SignupForm } from './Signup'
import { SIGNUP_STEPS } from './steps'

const dictionary = ja as Record<string, unknown>

const RUBY_MARK = /\{[^{}|]+\|[^{}]+\}/

function allStrings(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (value && typeof value === 'object') return Object.values(value).flatMap(allStrings)
  return []
}

describe('申し込みのフェーズは、ふりがななし', () => {
  it('辞書の signup・signup_complete・steps に、ふりがなの印がない', () => {
    for (const key of ['signup', 'signup_complete', 'steps']) {
      for (const text of allStrings(dictionary[key])) expect(text).not.toMatch(RUBY_MARK)
    }
  })

  it('申し込みページ・完了の画面・ステップに、ふりがな（<ruby>）が出ない', () => {
    const form = renderToStaticMarkup(
      <SignupForm
        plan={{ plan_name: '月額プラン', amount_jpy: 10000 }}
        canceled
        submitting={false}
        errorKey="error.email_mismatch"
        onSubmit={() => {}}
      />,
    )
    const complete = (status: 'confirming' | 'completed' | 'not_completed') =>
      renderToStaticMarkup(
        <MemoryRouter>
          <CompleteView status={status} loginId="s00001" />
        </MemoryRouter>,
      )
    const steps = renderToStaticMarkup(
      <StepNavigation labelKey="steps.label" steps={SIGNUP_STEPS} current={2} errorStep={2} />,
    )

    for (const html of [
      form,
      complete('confirming'),
      complete('completed'),
      complete('not_completed'),
      steps,
    ]) {
      expect(html).not.toContain('<ruby>')
    }
  })
})
