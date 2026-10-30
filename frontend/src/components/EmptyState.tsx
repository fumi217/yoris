import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

type Props = {
  icon: IconName
  title: ReactNode
  description?: ReactNode
}

/** まだ何もないときの表示：アイコン・一言・やわらかい説明を、中央に（デザインの決めごと 7 章。#382）。 */
export function EmptyState({ icon, title, description }: Props) {
  return (
    <div className="flex flex-col items-center gap-1 py-6 text-center">
      <Icon name={icon} className="mb-1 text-3xl text-field-line" />
      <p className="font-bold">{title}</p>
      {description && <p className="text-sm text-ink-sub">{description}</p>}
    </div>
  )
}
