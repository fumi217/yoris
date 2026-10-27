// 家族の「お問い合わせ」（AI に質問する）画面（UI-F05。spec 004 の T020）で使う型と、表示の決まり。
// API の形は specs/004-inquiry-agent/contracts/api.md の「家族の『質問する』」。

export type InquirySource = {
  kind: 'record' | 'reply'
  date: string // YYYY-MM-DD（日本時間）
  item: string | null // 記録の項目（record.item.* で引く）
  slot: string | null // 記録の区分（機嫌・眠りは "day"）
  theme_code: string | null // 返事のテーマ（theme.* の辞書のキー）
}

/**
 * 職員に渡した AI の発言の状態（backend/app/api/family/inquiry.py の HandoffOut。
 * 質問の種類そのものは、家族には返ってこない）。
 */
export type InquiryHandoff = {
  status: 'waiting' | 'answered'
  // 緊急（言葉の決まりで直した種類を含む）のときだけ true。画面は電話の案内も出す
  urgent: boolean
  // 同じ内容の対応待ちにつないだとき true。画面は「すでにお伝えしています」を出す（FR-016）
  already: boolean
}

export type InquiryMessage = {
  id: number
  sender: 'family' | 'ai' | 'staff'
  // 文。AI が答えなかったとき・根拠が非開示になったときは空（下の aiNoticeKey の文を出す）
  body: string
  created_at: string
  ai_result: 'answered' | 'handed_off' | 'no_record' | null
  sources: InquirySource[]
  hidden: boolean
  // 職員に渡した AI の発言だけ（それ以外の発言では null。古い API では、項目がないこともある）
  handoff?: InquiryHandoff | null
  // ここから職員の返事だけ（それ以外の発言では null）。名前は役割ではなく表示名。
  // 定型文はコード（辞書で引く）、書き足しは文字としてだけ出す
  staff_name: string | null
  template_codes: string[] | null
  note: string | null
  response_type: 'app' | 'phone' | null
}

export type SendResult = { family: InquiryMessage; ai: InquiryMessage }

// 1 回に読む件数（API の初期値と同じ）
export const PAGE_SIZE = 30

/** API は新しい順に返すので、画面に出す時刻の順（古い順）に並べ直す。 */
export function chronological(pages: InquiryMessage[][]): InquiryMessage[] {
  return [...pages.flat()].sort((a, b) => a.id - b.id)
}

/** 続きを読むときの before（読んだ中でいちばん古い id）。最後まで読んだら undefined。 */
export function nextBefore(lastPage: InquiryMessage[]): number | undefined {
  if (lastPage.length < PAGE_SIZE) return undefined
  return Math.min(...lastPage.map((message) => message.id))
}

/**
 * AI の発言で、本文の代わりに出す決まった文の辞書のキー。本文を出すときは null。
 * （答えなかった・根拠が非開示になったときは、API が本文を空で返す。data-model.md）
 */
export function aiNoticeKey(message: InquiryMessage): string | null {
  if (message.hidden) return 'inquiry.answer_hidden'
  // 同じ内容の対応待ちにつないだときは、「すでに」の文（FR-016）
  if (message.ai_result === 'handed_off') {
    return message.handoff?.already ? 'inquiry.already_handed_off' : 'inquiry.handed_off'
  }
  if (message.ai_result === 'no_record') return 'inquiry.no_record'
  return null
}

/**
 * 職員に渡した AI の発言に、電話の案内（「お急ぎのときは、施設にお電話ください」）を添えるか。
 * 緊急のときだけ添える（spec 004 の Edge Cases。今までは、渡したときは、いつも添えていた）。
 * 根拠が非開示になった答えには添えない。`handoff` がない古い API のときも、添えない。
 */
export function showsCallIfUrgent(message: InquiryMessage): boolean {
  return message.ai_result === 'handed_off' && !message.hidden && message.handoff?.urgent === true
}

/**
 * 画面に出たら、その発言のお知らせを読んだことにする発言か（Issue #244）。
 * アプリで返した職員の返事だけ。電話で対応した発言は、お知らせがないので、送らない。
 */
export function marksNoticeRead(message: InquiryMessage): boolean {
  return message.sender === 'staff' && message.response_type === 'app'
}

/** 「もとにした記録」の 1 つを、日付と辞書のキーの並びにする（例：10 月 23 日・食事・昼）。 */
export function sourceParts(source: InquirySource): {
  month: number
  day: number
  labelKeys: string[]
} {
  // 日付は文字のまま読む（Date にすると、ブラウザの時間帯で日がずれることがある）
  const [, month, day] = source.date.split('-').map(Number)
  if (source.kind === 'reply') {
    return { month, day, labelKeys: source.theme_code ? [source.theme_code] : [] }
  }
  const labelKeys = source.item ? [`record.item.${source.item}`] : []
  // 機嫌・眠りの区分（"day"）は出さない
  if (source.slot && source.slot !== 'day') labelKeys.push(`record.slot.${source.slot}`)
  return { month, day, labelKeys }
}
