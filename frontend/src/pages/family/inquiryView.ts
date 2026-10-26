// 家族の「お問い合わせ」（AI に質問する）画面（UI-F05。spec 004 の T020）で使う型と、表示の決まり。
// API の形は specs/004-inquiry-agent/contracts/api.md の「家族の『質問する』」。

export type InquirySource = {
  kind: 'record' | 'reply'
  date: string // YYYY-MM-DD（日本時間）
  item: string | null // 記録の項目（record.item.* で引く）
  slot: string | null // 記録の区分（機嫌・眠りは "day"）
  theme_code: string | null // 返事のテーマ（theme.* の辞書のキー）
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
  // ここから職員の返事だけ（004-T027・#87 で API に足す）
  staff_name?: string
  template_codes?: string[]
  note?: string | null
  response_type?: 'app' | 'phone'
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
  if (message.ai_result === 'handed_off') return 'inquiry.handed_off'
  if (message.ai_result === 'no_record') return 'inquiry.no_record'
  return null
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
