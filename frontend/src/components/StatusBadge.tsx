import type { ReactNode } from 'react'

export type StatusTone = 'neutral' | 'success' | 'warning'

// 色（デザインの決めごと 2.2 のラベル）。彩度は低くする。状態は、色だけでなく、必ず文字で示す（1.4.1）
const TONES: Record<StatusTone, string> = {
  // 未記録・一部など、落ち着いた状態（文字 ink-sub と primary-soft の比 4.89）
  neutral: 'bg-primary-soft text-ink-sub',
  // 済み・回答済み（文字 #166534・背景 #dcfce7。6.49）
  success: 'bg-[#dcfce7] text-[#166534]',
  // 待ち・注意（文字 #92400e・背景 #fef3c7。6.37）
  warning: 'bg-[#fef3c7] text-[#92400e]',
}

/** 小さな状態の印（未記録・記録済み・回答待ちなど）。中身は文字（辞書の文言）を渡す。 */
export function StatusBadge({
  tone = 'neutral',
  children,
}: {
  tone?: StatusTone
  children: ReactNode
}) {
  return (
    <span
      className={`inline-block shrink-0 rounded-full px-3 py-1 text-xs font-bold ${TONES[tone]}`}
    >
      {children}
    </span>
  )
}
