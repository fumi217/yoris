import { Icon } from '../../components/Icon'
import { StatusBadge } from '../../components/StatusBadge'
import { Text } from '../../components/Text'
import { themeDescKey, themeIconName, type FamilyTheme } from './requestsView'

type Props = {
  theme: FamilyTheme
  selected: boolean
  // 返事待ちのテーマ（同じテーマは、返事が届くまで、もう一度頼めない）
  waiting: boolean
  // 空きがなくて、これ以上選べない（選んでいるカードは、外せるので、false のまま）
  full: boolean
  onToggle: () => void
}

/**
 * 「知りたいこと」のテーマを選ぶカード（#385）。カード全体が押せる（小さなチェックだけを押させない）。
 * 選んでいる状態は、色だけでなく、右上のチェックの丸と太字・青い枠でも示す（1.4.1）。
 * 返事待ちのテーマは、押せず、「返信待ち」の文字を添える。押せないカード（返事待ち・空きがない）は、
 * 背景をグレーに・枠を破線にして、文字の薄さだけにしない（#387 ようこさん）。
 */
export function ThemeCard({ theme, selected, waiting, full, onToggle }: Props) {
  const disabled = waiting || (full && !selected)
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={onToggle}
      className={`relative flex min-h-24 w-full items-start gap-3 rounded-2xl border-2 p-4 pr-12 text-left ${
        disabled
          ? // 押せない：背景を `page` のグレーに、枠を破線に、文字を補足の色にする（文字の薄さだけにしない）
            'cursor-not-allowed border-dashed border-field-line bg-page text-ink-sub'
          : selected
            ? 'border-primary bg-primary-soft/40'
            : 'border-card-line bg-white'
      }`}
    >
      <span
        aria-hidden="true"
        className={`flex size-11 shrink-0 items-center justify-center rounded-full ${
          selected && !disabled ? 'bg-primary-soft text-primary' : 'bg-white text-ink-sub'
        }`}
      >
        <Icon name={themeIconName(theme.code)} className="text-xl" />
      </span>
      <span className="min-w-0 flex-1 space-y-1">
        {/* 縦に並べる枠の中で、ふりがなと文字が別々の行にならないよう、1 つにまとめる */}
        <span className={`block font-bold ${disabled ? 'text-ink-sub' : ''}`}>
          <Text k={theme.code} />
        </span>
        <span className="block text-sm text-ink-sub">
          <Text k={themeDescKey(theme.code)} />
        </span>
        {waiting && (
          <span className="block">
            <StatusBadge tone="warning">
              <Text k="requests.status_waiting_short" />
            </StatusBadge>
          </span>
        )}
      </span>
      {/* 右上：選んでいないときは空の丸、選んでいるときは青のチェックの丸（飾り。状態は aria-pressed で伝える） */}
      <span aria-hidden="true" className="absolute top-4 right-4">
        {selected ? (
          <Icon name="checked" className="text-2xl text-primary" />
        ) : (
          <span className="block size-6 rounded-full border-2 border-field-line bg-white" />
        )}
      </span>
    </button>
  )
}
