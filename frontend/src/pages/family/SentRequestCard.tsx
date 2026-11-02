import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { Icon } from '../../components/Icon'
import { StatusBadge, type StatusTone } from '../../components/StatusBadge'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import {
  replyLinkFor,
  sentAtParts,
  statusKeyOf,
  themeIconName,
  type FamilyRequest,
} from './requestsView'

const BADGE: Record<FamilyRequest['status'], { key: string; tone: StatusTone }> = {
  answered: { key: 'requests.badge_answered', tone: 'success' },
  waiting: { key: 'requests.badge_waiting', tone: 'warning' },
  cancelled: { key: 'requests.badge_cancelled', tone: 'neutral' },
}

type Props = {
  request: FamilyRequest
  // 取り消している最中（押せなくする）
  cancelling: boolean
  onCancel: () => void
}

/**
 * 送ったリクエストの 1 件（横長のカード。#385）。左にテーマのアイコン（状態で変えない。状態は右の印だけで示す）、テーマ・状態の説明・送った日時（◯日前）、
 * 右に状態の印（返信あり＝淡い緑／返信待ち＝淡いオレンジ。文字でも示す。受け取った側の言い方にする。#387）。
 * 返事の前は取り消せる。返事が届いたら「連絡帳で見る」。3 日たっても返事がなければ、電話の案内（FR-014）。
 */
export function SentRequestCard({ request, cancelling, onCancel }: Props) {
  const { t } = useTranslation()
  const badge = BADGE[request.status]
  return (
    <li className="flex flex-wrap items-start gap-3 rounded-2xl border border-card-line bg-white p-4 shadow-sm">
      <span
        aria-hidden="true"
        className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary"
      >
        <Icon name={themeIconName(request.theme_code)} className="text-xl" />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-bold">
          <Text k={request.theme_code} />
        </p>
        <p className="text-sm">
          <Text k={statusKeyOf(request)} />
        </p>
        <p className="text-sm text-ink-sub">
          <Ruby text={t('requests.sent_at', sentAtParts(request.created_at))} />（
          <Ruby
            text={
              request.days_ago === 0
                ? t('requests.days_ago_zero')
                : t('requests.days_ago', { count: request.days_ago })
            }
          />
          ）
        </p>
        {request.status === 'waiting' && request.overdue && (
          <p className="text-sm font-bold text-red-700">
            <Text k="requests.overdue" />
          </p>
        )}
        {request.status === 'waiting' && (
          <button
            type="button"
            disabled={cancelling}
            onClick={onCancel}
            className="mt-1 min-h-11 rounded-xl border border-field-line bg-page px-4 text-sm font-bold text-ink shadow-sm disabled:opacity-50"
          >
            <Text k="requests.cancel" />
          </button>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-2">
        <StatusBadge tone={badge.tone}>
          <Text k={badge.key} />
        </StatusBadge>
        {request.status === 'answered' && (
          <Link
            to={replyLinkFor(request)}
            className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary underline"
          >
            <Text k="requests.see_reply" />
            <Icon name="next" />
          </Link>
        )}
      </div>
    </li>
  )
}
