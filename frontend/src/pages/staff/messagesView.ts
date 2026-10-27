// 職員の「家族からのメッセージ」（UI-S08・UI-S09）の、API の形と、表示を決める部分（spec 004 の T029）。
// 画面（FamilyMessages.tsx・FamilyMessage.tsx）と分けて、単体でテストできるようにしている。

/** 担当の職員（backend/app/api/staff/messages.py の AssigneeOut）。 */
export type Assignee = { id: number; display_name: string }

/** 一覧の 1 行（StaffMessageRow）。 */
export type MessageRow = {
  id: number
  resident_id: number
  // 入居者の呼び名。辞書を通さず、そのまま出す
  resident_display_name: string
  category: 'medical' | 'complaint' | 'money' | 'care_request' | 'urgent' | 'other'
  assignee: Assignee | null
  // AI がまとめた要約。辞書を通さず、文字としてだけ出す（FR-028）
  summary: string
  status: 'waiting' | 'answered'
  handed_at: string
  elapsed_days: number
  waiting_over_a_day: boolean
}

export type MessageList = { messages: MessageRow[] }

/** 会話の 1 件（ConversationMessageOut）。 */
export type ConversationMessage = {
  id: number
  sender: 'family' | 'ai' | 'staff'
  body: string
  created_at: string
  // 職員の返事だけ：選んだ定型文のコードと、書き足した文
  template_codes: string[] | null
  note: string | null
}

export type StaffTemplate = { id: number; code: string }

/** 詳細（StaffMessageDetail）。 */
export type MessageDetail = MessageRow & {
  origin: ConversationMessage
  previous: ConversationMessage[]
  follow_ups: ConversationMessage[]
  templates: StaffTemplate[]
}

export type Status = 'waiting' | 'answered'

/** 一覧の絞り込み（対応待ち／対応済み）。 */
export const STATUS_TABS: Status[] = ['waiting', 'answered']

/**
 * 画面の URL の頭。職員の画面から開いたときと、管理画面から開いたときで、同じ画面を使い分ける
 * （事務員は管理画面からだけ開ける。docs/画面設計.md「2」・#88）。
 */
export function messagesBase(pathname: string): '/staff/messages' | '/admin/messages' {
  return pathname.startsWith('/admin') ? '/admin/messages' : '/staff/messages'
}

/**
 * URL の `?resident_id=` から、絞り込む入居者の id を読む。
 * 正の整数だけを受け付ける（それ以外・複数・空は絞り込まない）。API には、読めた数だけを渡す。
 * 安全な整数の範囲（`Number.MAX_SAFE_INTEGER`）を超える数は、`Number()` で丸められて別の値になるので、
 * 読まない（PR #241 ようこ）。
 * 入居者の id が合っていても、見られるメッセージは API が決める（苦情は生活相談員・施設長にだけ）。
 */
export function residentFilterOf(search: string): number | null {
  const values = new URLSearchParams(search).getAll('resident_id')
  if (values.length !== 1 || !/^[1-9][0-9]*$/.test(values[0])) return null
  const id = Number(values[0])
  return Number.isSafeInteger(id) ? id : null
}

/** 一覧の API の URL。入居者で絞るときは、`resident_id` を足す。 */
export function listUrl(status: Status, residentId: number | null): string {
  const query = new URLSearchParams({ status })
  if (residentId !== null) query.set('resident_id', String(residentId))
  return `/api/staff/messages?${query.toString()}`
}

/** 質問の種類の名前の辞書のキー。 */
export function categoryKey(category: MessageRow['category']): string {
  return `inquiry.category.${category}`
}

/** 受け付けてからの日数の文の辞書のキー（0 日は「今日」）。 */
export function arrivedKey(days: number): string {
  return days <= 0 ? 'family_messages.arrived_today' : 'family_messages.arrived_days'
}

/** 発言をした人の名前の辞書のキー。 */
export function senderKey(sender: ConversationMessage['sender']): string {
  return `family_messages.sender_${sender}`
}

/** 「自分が対応する」を出すか：まだ担当がいない対応待ちのときだけ（FR-012b）。 */
export function canAssign(message: Pick<MessageRow, 'assignee' | 'status'>): boolean {
  return message.assignee === null && message.status === 'waiting'
}

/** 返事の欄を出すか：対応待ちのときだけ（対応済みになったら出さない。FR-017）。 */
export function canReply(message: Pick<MessageRow, 'status'>): boolean {
  return message.status === 'waiting'
}

/** 返事の欄に出す定型文。苦情には用意がない（FR-014）ので、空なら電話の案内を出す。 */
export function hasTemplates(templates: StaffTemplate[]): boolean {
  return templates.length > 0
}

/** `GET /api/staff/messages/count` の結果（施設全体の対応待ち。苦情は生活相談員・施設長にだけ数える）。 */
export type MessageCount = { count: number }

/** 画面で読んだ「家族からのメッセージ」の置き場所の頭（担当・返事のあとに、まとめて読み直す）。 */
export const MESSAGES_KEY = ['staff', 'messages'] as const
