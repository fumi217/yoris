import type { ElementType, ReactNode } from 'react'

type Props = {
  children: ReactNode
  // 出す要素（見出しのある区切りなら section など。ふつうは div）
  as?: ElementType
  className?: string
}

/**
 * 白いカード（デザインの決めごと 7 章。#382）。角丸は大きめ、枠は薄い（card-line）、影はごく弱い。
 * カードの中にカードを重ねない（中の区切りは、薄い線か余白で分ける）。
 */
export function Card({ children, as: Tag = 'div', className = '' }: Props) {
  return (
    <Tag className={`rounded-2xl border border-card-line bg-white p-5 shadow-sm ${className}`}>
      {children}
    </Tag>
  )
}
