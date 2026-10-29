// 職員の「写真を載せる」画面の、選んだ写真の管理（spec 005 の 005-T014。research.md R-01）。
// 画面から分けてあるのは、10 枚まで・10MB の確認・状態の変化を、テストしやすくするため。

import { ApiError } from '../../api/client'

/** 1 回に選べる写真の枚数（Issue の完了条件・R-01）。 */
export const MAX_PHOTOS = 10
/** 1 枚の大きさの上限。サーバーでも断る（FR-003）が、送る前に画面でも断る。 */
export const MAX_BYTES = 10 * 1024 * 1024
/** 一言コメントの文字数の上限（任意）。 */
export const MAX_COMMENT = 100
/** 選べる形式（PDF は選べない）。 */
export const ACCEPT = 'image/jpeg,image/png'

export type UploadStatus = 'waiting' | 'sending' | 'done' | 'failed'

export type UploadItem = {
  id: number
  file: File
  // 任意（空でよい）。職員が自由に書いた文
  comment: string
  status: UploadStatus
  // 失敗したときの文言の辞書のキー
  errorKey: string | null
  // もう一度送れるか。画面で断った写真（大きすぎる・形式が違う）は送り直せない
  retryable: boolean
}

/** 送る前に断る理由の辞書のキー。問題がなければ null。 */
export function problemOf(file: Pick<File, 'size' | 'type'>): string | null {
  if (!ACCEPT.split(',').includes(file.type)) return 'album_upload.bad_type'
  if (file.size > MAX_BYTES) return 'album_upload.too_big'
  return null
}

/** コメントが長すぎるか（文字数で数える。絵文字なども 1 文字）。 */
export function commentTooLong(comment: string): boolean {
  return Array.from(comment).length > MAX_COMMENT
}

/**
 * 選んだ写真を足す。送れる写真（待ち・送信中・失敗して送り直せるもの）と合わせて 10 枚まで。
 * 載せ終わった写真と、画面で断った写真（形式が違う・大きすぎる）は、10 枚の数に入れない
 * （断られた写真が、10 枚の枠を使い続けないように）。超えた分は足さず、skipped に数える。
 * 形式が違う・大きすぎる写真は、送らずに失敗の印を付ける。
 */
export function addFiles(
  items: UploadItem[],
  files: File[],
  nextId: number,
): { items: UploadItem[]; nextId: number; skipped: number } {
  const open = items.filter(
    (item) => item.status !== 'done' && !(item.status === 'failed' && !item.retryable),
  ).length
  const room = Math.max(0, MAX_PHOTOS - open)
  const added: UploadItem[] = files.slice(0, room).map((file, index) => {
    const problem = problemOf(file)
    return {
      id: nextId + index,
      file,
      comment: '',
      status: problem ? 'failed' : 'waiting',
      errorKey: problem,
      retryable: problem === null,
    }
  })
  return {
    items: [...items, ...added],
    nextId: nextId + added.length,
    skipped: files.length - added.length,
  }
}

export function updateItem(
  items: UploadItem[],
  id: number,
  patch: Partial<Omit<UploadItem, 'id' | 'file'>>,
): UploadItem[] {
  return items.map((item) => (item.id === id ? { ...item, ...patch } : item))
}

export function removeItem(items: UploadItem[], id: number): UploadItem[] {
  return items.filter((item) => item.id !== id)
}

/** 次に送る写真（待ちのうち、いちばん前）。なければ undefined。 */
export function nextToSend(items: UploadItem[]): UploadItem | undefined {
  return items.find((item) => item.status === 'waiting')
}

/** 失敗した写真を、もう一度送れる状態（待ち）に戻す。送り直せない写真は、そのまま。 */
export function retryItem(items: UploadItem[], id: number): UploadItem[] {
  return items.map((item) =>
    item.id === id && item.status === 'failed' && item.retryable
      ? { ...item, status: 'waiting', errorKey: null }
      : item,
  )
}

/** 「送る」を押せるか（送るものがあり、いま送っているものがない）。コメントが長すぎるものは、押せない。 */
export function canSend(items: UploadItem[]): boolean {
  return (
    items.some((item) => item.status === 'waiting') &&
    !items.some((item) => item.status === 'sending') &&
    !items.some((item) => item.status === 'waiting' && commentTooLong(item.comment))
  )
}

/** 載せた枚数と、全部の枚数。 */
export function progress(items: UploadItem[]): { done: number; total: number } {
  return { done: items.filter((item) => item.status === 'done').length, total: items.length }
}

/**
 * 送るのに失敗したときの文言のキー。
 * invalid_file は、アルバムでは JPG・PNG だけ（辞書の既定の文言は PDF も含むので、専用の文言を使う）。
 */
export function errorKeyFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'invalid_file') return 'album_upload.invalid_file'
    if (error.code === 'validation_error') return 'album_upload.validation_error'
    return error.messageKey
  }
  return 'error.server_error'
}
