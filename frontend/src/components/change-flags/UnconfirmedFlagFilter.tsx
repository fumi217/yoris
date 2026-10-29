import { useTranslation } from 'react-i18next'
import { Ruby } from '../../i18n/Ruby'

type Props = {
  // まだ確かめていない目印がある入居者の人数（`unconfirmed_flag_count`）
  count: number
  // 目印の付いた入居者だけに絞っているか
  active: boolean
  onToggle: () => void
}

/**
 * 入居者一覧の上に置く「確かめていない目印：◯件」（spec 006 の 006-T014・FR-003）。
 * 押すと、目印の付いた入居者だけに絞れる。もう一度押すと、元に戻る。
 * 絞っているかは、色だけでなく ✔ と太字でも示す（アクセシビリティ）。
 * 目印だけの別の画面は作らず、通知や音も出さない（FR-005）。
 */
export function UnconfirmedFlagFilter({ count, active, onToggle }: Props) {
  const { t } = useTranslation()
  return (
    <button
      type="button"
      aria-pressed={active}
      // 目印がなくて絞っていないときは、押しても何も変わらない
      disabled={count === 0 && !active}
      onClick={onToggle}
      className={`min-h-11 rounded border-2 px-3 py-2 text-left disabled:opacity-60 ${
        active ? 'border-amber-700 bg-amber-100 font-bold' : 'border-gray-500 bg-white'
      }`}
    >
      {active && '✔ '}
      <Ruby text={t('change.unconfirmed_count', { count })} />
    </button>
  )
}
