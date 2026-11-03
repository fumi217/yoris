// 様子のメモを書く画面（UI-S05）の、API の形と、判定・エラーの文言を決める部分（spec 007 の T011）。
// 画面（MemoEditor.tsx。大文字・小文字だけの違いのファイル名は、Windows で同じに見えるので、Logic を付けた）と分けて、単体でテストできるようにしている。

import { ApiError, messageKeyOf } from '../../api/client'
import type { StaffRole } from '../../auth/me'

/** 原文の言語（backend/app/models/memos.py の SOURCE_LANGS。research.md R-12）。 */
export const SOURCE_LANGS = ['ja', 'id', 'en'] as const
export type SourceLang = (typeof SOURCE_LANGS)[number]

/** メモ 1 つ（backend/app/api/staff/memos.py の MemoOut）。原文・整えた日本語は、文字としてだけ出す。 */
export type Memo = {
  id: number
  resident_id: number
  memo_date: string
  written_at: string
  source_lang: SourceLang
  original_text: string
  rewritten_text: string | null
  back_translation: string | null
  warnings: string[]
  status: 'draft' | 'pending' | 'approved' | 'returned' | 'withdrawn'
  return_reason: string | null
}

// 原文の文字数の上限（backend の ORIGINAL_MAX。FR-001）
export const ORIGINAL_MAX = 500

/** 書く画面を開いたときの、原文の言語の初期値は、職員の表示言語（扱えない言語なら日本語。R-12）。 */
export function initialLang(language: string | undefined): SourceLang {
  return (SOURCE_LANGS as readonly string[]).includes(language ?? '')
    ? (language as SourceLang)
    : 'ja'
}

/** 原文の文字数（前後の空白は数えない。絵文字なども 1 文字。backend の数え方と同じ）。 */
export function originalLength(text: string): number {
  return Array.from(text.trim()).length
}

/** 「日本語にする」を押せない理由。押せるなら null。 */
export function originalProblem(text: string): 'empty' | 'too_long' | null {
  const length = originalLength(text)
  if (length === 0) return 'empty'
  if (length > ORIGINAL_MAX) return 'too_long'
  return null
}

/**
 * 押した操作が、メモの状態に合わなかった（409 `invalid_state`）か。
 * 別の画面で、確かめました・取り下げる・承認・戻すが先に済んでいたときや、
 * 整えた日本語・訳し戻しがまだないのに「確かめました」を押したときに返る（backend の `_move_own`）。
 */
export function isStateChanged(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'invalid_state'
}

/**
 * 失敗したときに出す文言の辞書のキー。AI が止まったとき（503 `ai_unavailable`）は、
 * 書く画面の文言（「いま日本語にできません…」）を出す。ほかは、共通のエラーの文言
 * （メモの状態が変わっていた 409 `invalid_state` も、共通の「いまの状態では、この操作はできません」。
 * 画面は、あわせて最新の状態に入れ替える。MemoEditor の onError）。
 */
export function errorKeyFor(error: unknown): string {
  if (error instanceof ApiError && error.code === 'ai_unavailable') return 'memo.unavailable'
  return messageKeyOf(error)
}

/** 原文の言語の名前の辞書のキー。 */
export function langKey(lang: SourceLang): string {
  return `memo.lang.${lang}`
}

/**
 * 様子のメモを書ける役割（介護職員・リーダー。backend の WRITERS と同じ。contracts/api.md）。
 * 役割の判定はここだけに置く（記録の画面の「様子のメモを書く」ボタンも使う。#254・#94）。
 * 役割がまだ分からない（読み込み中）ときは false。
 */
export function isMemoWriter(role: StaffRole | null | undefined): boolean {
  return role === 'care_worker' || role === 'leader'
}

export type MemoStatus = Memo['status']

/** 整えた日本語の文字数の上限（backend の REWRITTEN_MAX。FR-008）。 */
export const REWRITTEN_MAX = 1000

/** 直せる状態（下書き・戻された。backend の EDITABLE_STATUSES と同じ）。 */
export function isEditable(status: MemoStatus): boolean {
  return status === 'draft' || status === 'returned'
}

/** 取り下げられる状態（承認済みは、リーダーが公開を取り下げる。FR-010）。 */
export function canWithdraw(status: MemoStatus): boolean {
  return status === 'draft' || status === 'pending' || status === 'returned'
}

/** 状態の名前の辞書のキー。 */
export function statusKey(status: MemoStatus): string {
  return `memo.status.${status}`
}

/** 機械の目の印（backend の WARNINGS）。急ぐもの・目立たせるものから並べる。 */
const WARNING_ORDER = [
  'urgent_words',
  'medical_added',
  'medical_in_original',
  'other_name',
  'length_changed',
] as const

/** 印を、決めた順に並べて、辞書のキーにする。知らない印は出さない。 */
export function warningKeys(warnings: readonly string[]): string[] {
  return WARNING_ORDER.filter((code) => warnings.includes(code)).map(
    (code) => `memo.warning.${code}`,
  )
}

/** 文字数（前後の空白は数えない。絵文字なども 1 文字）。 */
export function textLength(text: string): number {
  return Array.from(text.trim()).length
}

/** 整えた日本語を直したとき、保存できない理由。保存できるなら null。 */
export function rewrittenProblem(text: string): 'empty' | 'too_long' | null {
  const length = textLength(text)
  if (length === 0) return 'empty'
  if (length > REWRITTEN_MAX) return 'too_long'
  return null
}

/** 画面に出ている原文を、保存した原文から直したか。 */
export function originalChanged(memo: Memo, text: string): boolean {
  return text.trim() !== memo.original_text
}

/** 画面に出ている整えた日本語を、保存した文から直したか。 */
export function rewrittenChanged(memo: Memo, text: string): boolean {
  return text.trim() !== (memo.rewritten_text ?? '')
}

/**
 * 「確かめました」を押せるか（backend の confirm の条件と同じ。FR-009）。
 * 整えた日本語があり、日本語以外の職員は訳し戻しもあること。直したのに保存していない文があるときは、
 * 古い訳し戻しを見て確かめることになるので、押せない。
 */
export function canConfirm(
  memo: Memo,
  staffLanguage: string | undefined,
  edits: { original: string; rewritten: string },
): boolean {
  if (!isEditable(memo.status) || memo.rewritten_text === null) return false
  if (originalChanged(memo, edits.original) || rewrittenChanged(memo, edits.rewritten)) return false
  return staffLanguage === 'ja' || memo.back_translation !== null
}

/** 日本語の職員は訳し戻さない（backend が 409 にする。FR-007）。 */
export function needsBackTranslation(staffLanguage: string | undefined): boolean {
  return staffLanguage !== 'ja'
}

/**
 * 書く画面を、そのまま出してよいか（false なら「書けません」の案内を出す）。
 * 守りは API の 403。ここは、書いてから 403 になって手間がむだにならないよう、最初に案内するため。
 * 役割がまだ分からない（読み込み中）ときは、案内を出さない（true）。
 */
export function canWriteMemo(role: StaffRole | null | undefined): boolean {
  return role === undefined || isMemoWriter(role)
}
