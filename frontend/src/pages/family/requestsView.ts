// 「知りたいこと」の画面（Requests.tsx）の、表示を決める部分。画面と分けて、単体でテストできるようにしている。
import { ApiError, messageKeyOf } from '../../api/client'

// emoji は API が返すが、画面には出さない（アイコンを使う。#385）
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
  // 返事が入った連絡帳の日付（"2026-10-26"。返事のないものは null。#403）。
  // 古い API では、項目がないこともある
  reply_date?: string | null
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

// 返事待ちにできる件数（spec 001 の FR-014。backend の MAX_WAITING_REQUESTS と同じ）
export const MAX_WAITING = 3

/** あと何件、選んで送れるか（3 件から、いま返事待ちの件数を引いた数）。 */
export function remainingSlots(requests: FamilyRequest[]): number {
  const waiting = requests.filter((request) => request.status === 'waiting').length
  return Math.max(0, MAX_WAITING - waiting)
}

/**
 * テーマを選ぶ・外す。選んでいれば外し、選んでいなければ足す。ただし、空き（remaining）の数までしか選べない
 * （足りないときは、そのまま。spec 001 の FR-014・Session 2026-10-30）。
 */
export function toggleTheme(selected: number[], themeId: number, remaining: number): number[] {
  if (selected.includes(themeId)) return selected.filter((id) => id !== themeId)
  return selected.length < remaining ? [...selected, themeId] : selected
}

// テーマのアイコンは、家族・職員・管理画面で共通（components/themeIcon.ts）
export { themeIconName } from '../../components/themeIcon'

/** テーマの説明の辞書のキー（`theme.daily_life` → `theme_desc.daily_life`）。 */
export function themeDescKey(code: string): string {
  return code.replace(/^theme\./, 'theme_desc.')
}

/**
 * 選んだテーマを、1 つずつ順に送る途中で止まったときのエラー。何件送れたか（sent）と、止めた理由（cause）を持つ。
 * 止まったら、残りは送らない（上限・同じテーマなど。spec 001 の Session 2026-10-30）。
 */
export class SendStopped extends Error {
  sent: number
  cause: unknown
  // 送れたテーマの id（送った順。「『普段の様子』は送れましたが…」と、名前で案内するため）
  sentThemeIds: number[]
  constructor(sent: number, cause: unknown, sentThemeIds: number[] = []) {
    super('send stopped')
    this.sent = sent
    this.cause = cause
    this.sentThemeIds = sentThemeIds
  }
}

/** 順に送る途中で止まったときの、送れたテーマの id（止まったのでなければ空）。 */
export function sentThemeIdsBeforeStop(error: unknown): number[] {
  return error instanceof SendStopped ? error.sentThemeIds : []
}

/** 返事待ちが上限のとき・同じテーマのときなどの、エラーの文言のキー（止めた理由から）。 */
export function sendErrorKey(error: unknown): string {
  return messageKeyOf(error instanceof SendStopped ? error.cause : error)
}

/** 順に送る途中で止まったときの、送れた件数（止まったのでなければ 0）。 */
export function sentBeforeStop(error: unknown): number {
  return error instanceof SendStopped ? error.sent : 0
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

/**
 * 「連絡帳で見る」の行き先。返事が入った日の連絡帳（`/family?date=`）。日付が分からないとき
 * （古い API・形の合わない値）は、今日の連絡帳（#403）。
 */
export function replyLinkFor(request: Pick<FamilyRequest, 'reply_date'>): string {
  const date = request.reply_date
  return date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? `/family?date=${date}` : '/family'
}
