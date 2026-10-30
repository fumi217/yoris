import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

type Props = {
  icon: IconName
  // 見出し（h2）。呼ぶ側で Text などを渡す
  title: ReactNode
  // 見出しの下の短い説明
  description?: ReactNode
  // 右に置くもの（StatusBadge など）
  aside?: ReactNode
}

/** 区切りの見出し：丸いアイコン・見出し・説明・右の状態の印（デザインの決めごと 7 章。#382）。
 * 説明は、見出しと印の下に、幅いっぱいで出す（印に幅を取られて、不自然な位置で折り返さないように）。 */
export function SectionHeader({ icon, title, description, aside }: Props) {
  return (
    <div className="space-y-1 break-keep">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary"
        >
          <Icon name={icon} className="text-lg" />
        </span>
        <h2 className="min-w-0 flex-1 text-lg font-bold">{title}</h2>
        {aside}
      </div>
      {description && <p className="text-sm text-ink-sub">{description}</p>}
    </div>
  )
}
