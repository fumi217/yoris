import { useTranslation } from 'react-i18next'
import { Icon } from '../Icon'
import { Ruby } from '../../i18n/Ruby'

type Props = {
  // まだ確かめていない目印がある入居者の人数（`unconfirmed_flag_count`）
  count: number
  // まだ確かめていない目印のある入居者だけに絞っているか
  active: boolean
  onToggle: () => void
}

/**
 * 入居者一覧の上に置く「確かめていない目印：◯件」（spec 006 の 006-T014・FR-003）。
 * 押すと、まだ確かめていない目印のある入居者だけに絞れる（件数と行数が一致する）。もう一度押すと、元に戻る。
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
      className={`min-h-11 rounded-full border px-4 py-2 text-left text-sm font-bold disabled:opacity-60 ${
        active ? 'border-primary bg-primary text-white' : 'border-field-line bg-card'
      }`}
    >
      <Icon name={active ? 'check' : 'warning'} className="mr-1" />
      <Ruby text={t('change.unconfirmed_count', { count })} />
    </button>
  )
}
