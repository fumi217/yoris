import type { Step } from '../../components/StepNavigation'

/** 申し込みの流れ（入力 → お支払い → 完了）。申し込みページと完了の画面に出す。 */
export const SIGNUP_STEPS: Step[] = [
  { titleKey: 'steps.signup.entry' },
  { titleKey: 'steps.signup.payment' },
  { titleKey: 'steps.signup.done' },
]
