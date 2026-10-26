// 「知りたいこと」の画面（Requests.tsx）の、表示を決める部分。画面と分けて、単体でテストできるようにしている。
import { ApiError, messageKeyOf } from '../../api/client'

export type FamilyTheme = { id: number; code: string; emoji: string }

export type FamilyRequest = {
  id: number
  theme_id: number
  theme_code: string
  emoji: string
  status: 'waiting' | 'answered' | 'cancelled'
  created_at: string
  days_ago: number
  overdue: boolean
}

/**
 * 送った日時を、月・日・時刻に分ける（施設の日本時間で出す）。「月」「日」は辞書（requests.sent_at）に書く。
 * コードに直接書くと、ふりがなの付け直し（001-T083）で漏れるため。
 */
export function sentAtParts(iso: string): { month: string; day: string; time: string } {
  const parts = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(iso))
  const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return { month: pick('month'), day: pick('day'), time: `${pick('hour')}:${pick('minute')}` }
}

/**
 * 取り消しに失敗したときの文言のキー。返事がついたあとの取り消し（409 already_replied）だけは、
 * 職員向けの error.already_replied ではなく、家族向けの専用の文言を出す（#135）。
 */
export function cancelErrorKey(error: unknown): string {
  if (error instanceof ApiError && error.code === 'already_replied') {
    return 'requests.cancel_after_reply'
  }
  return messageKeyOf(error)
}

/** 返事を待っているテーマ。同じテーマは、返事が届くまで、もう一度頼めない。 */
export function waitingThemeIds(requests: FamilyRequest[]): Set<number> {
  return new Set(requests.filter((request) => request.status === 'waiting').map((r) => r.theme_id))
}

/** 一覧の 1 件に出す、状態の文言のキー。 */
export function statusKeyOf(request: FamilyRequest): string {
  if (request.status === 'answered') return 'requests.status_answered'
  if (request.status === 'cancelled') return 'requests.status_cancelled'
  return 'requests.status_waiting'
}
