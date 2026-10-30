import { useTranslation } from 'react-i18next'
import { Ruby } from '../i18n/Ruby'

export type Step = {
  // 辞書のキー（ステップのタイトル）
  titleKey: string
}

type Props = {
  // 全体の名前（辞書のキー）。スクリーンリーダーに、何の流れかを伝える
  labelKey: string
  steps: Step[]
  // 今いるステップ（1 から数える）。これより前のステップは「完了」、後ろは「まだ」
  current: number
  // うまくいかなかったステップ（1 から数える）。そのステップに ! を付ける
  errorStep?: number
}

/**
 * ステップナビゲーション（デジタル庁デザインシステム DADS の考え方に沿った、表示だけの部品）。
 * 手続きの流れ（例：入力 → お支払い → 完了）の、今いる場所を見せる。押して移ることはできない。
 *
 * - 今のステップに `aria-current="true"`。全体の進み具合は、見えない文で伝える（例：全3ステップ中、2ステップ目）
 * - 色だけに頼らない：完了はチェック、エラーは !、今のステップは濃い丸と太い文字、番号も出す
 * - 参考：https://design.digital.go.jp/dads/components/step-navigation/
 */
export function StepNavigation({ labelKey, steps, current, errorStep }: Props) {
  const { t } = useTranslation()
  return (
    <div role="group" aria-label={t(labelKey)}>
      <p className="sr-only">
        <Ruby text={t('steps.summary', { total: steps.length, current })} />
      </p>
      <ol className="flex">
        {steps.map((step, index) => {
          const number = index + 1
          const state = stateOf(number, current, errorStep)
          return (
            <li
              key={step.titleKey}
              aria-current={number === current ? 'true' : undefined}
              data-state={state}
              className="relative flex flex-1 flex-col items-center gap-1 text-center"
            >
              {/* 前のステップの丸とつなぐ線（最初のステップにはない） */}
              {number > 1 && (
                <span
                  aria-hidden="true"
                  className={`absolute top-4 -left-1/2 h-0.5 w-full ${
                    number <= current ? 'bg-gray-600' : 'bg-gray-300'
                  }`}
                />
              )}
              <span className="sr-only">
                <Ruby text={t('steps.step')} />
              </span>
              <span
                className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 font-bold ${circleClass[state]}`}
              >
                {state === 'completed' ? '✓' : state === 'error' ? '!' : number}
                {state === 'completed' && (
                  <span className="sr-only">
                    <Ruby text={t('steps.completed')} />
                  </span>
                )}
                {state === 'error' && (
                  <span className="sr-only">
                    <Ruby text={t('steps.error')} />
                  </span>
                )}
              </span>
              <span className={`text-sm ${state === 'current' ? 'font-bold' : ''}`}>
                <Ruby text={t(step.titleKey)} />
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

type State = 'completed' | 'current' | 'upcoming' | 'error'

function stateOf(number: number, current: number, errorStep?: number): State {
  if (number === errorStep) return 'error'
  if (number < current) return 'completed'
  if (number === current) return 'current'
  return 'upcoming'
}

const circleClass: Record<State, string> = {
  completed: 'border-gray-600 bg-gray-600 text-white',
  current: 'border-primary bg-primary text-white',
  upcoming: 'border-ink-sub bg-white text-gray-600',
  error: 'border-red-700 bg-red-700 text-white',
}
