import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/client'
import {
  MAX_BYTES,
  MAX_PHOTOS,
  addFiles,
  canSend,
  commentTooLong,
  errorKeyFor,
  nextToSend,
  problemOf,
  progress,
  removeItem,
  retryItem,
  updateItem,
} from './albumUploadLogic'

const file = (type = 'image/png', size = 100) => ({ type, size }) as File
const files = (count: number) => Array.from({ length: count }, () => file())

describe('problemOf', () => {
  it('JPG・PNG の 10MB 以下は、問題なし', () => {
    expect(problemOf(file('image/jpeg'))).toBeNull()
    expect(problemOf(file('image/png', MAX_BYTES))).toBeNull()
  })

  it('PDF などの形式と、10MB を超える写真は、送る前に断る', () => {
    expect(problemOf(file('application/pdf'))).toBe('album_upload.bad_type')
    expect(problemOf(file('image/gif'))).toBe('album_upload.bad_type')
    expect(problemOf(file('image/png', MAX_BYTES + 1))).toBe('album_upload.too_big')
  })
})

describe('addFiles', () => {
  it('選んだ写真が、待ちの状態で足される', () => {
    const { items, nextId, skipped } = addFiles([], files(2), 1)

    expect(items.map((item) => [item.id, item.status])).toEqual([
      [1, 'waiting'],
      [2, 'waiting'],
    ])
    expect(nextId).toBe(3)
    expect(skipped).toBe(0)
  })

  it('まだ載せていない写真は、合わせて 10 枚まで。超えた分は足さない', () => {
    const first = addFiles([], files(8), 1)
    const second = addFiles(first.items, files(5), first.nextId)

    expect(second.items).toHaveLength(MAX_PHOTOS)
    expect(second.skipped).toBe(3)
  })

  it('載せ終わった写真は、10 枚の数に入れない（続けて、また選べる）', () => {
    const first = addFiles([], files(10), 1)
    const allDone = first.items.map((item) => ({ ...item, status: 'done' as const }))

    const second = addFiles(allDone, files(3), first.nextId)

    expect(second.skipped).toBe(0)
    expect(second.items).toHaveLength(13)
  })

  it('断られた写真（送り直せない失敗）は、10 枚の数に入れない', () => {
    const first = addFiles([], [file('application/pdf'), file('application/pdf')], 1)

    const second = addFiles(first.items, files(10), first.nextId)

    expect(second.skipped).toBe(0)
    expect(second.items.filter((item) => item.status === 'waiting')).toHaveLength(10)
  })

  it('形式が違う・大きすぎる写真は、送らずに失敗の印を付け、送り直せない', () => {
    const { items } = addFiles([], [file('application/pdf'), file('image/png', MAX_BYTES + 1)], 1)

    expect(items.map((item) => [item.status, item.errorKey, item.retryable])).toEqual([
      ['failed', 'album_upload.bad_type', false],
      ['failed', 'album_upload.too_big', false],
    ])
    expect(nextToSend(items)).toBeUndefined() // 送る写真にならない
  })
})

describe('状態の変化', () => {
  const base = addFiles([], files(3), 1).items

  it('次に送るのは、待ちのうち、いちばん前の写真', () => {
    expect(nextToSend(base)?.id).toBe(1)
    const sent = updateItem(base, 1, { status: 'done' })
    expect(nextToSend(sent)?.id).toBe(2)
  })

  it('失敗した写真だけ、もう一度送れる状態（待ち）に戻る', () => {
    const failed = updateItem(base, 2, {
      status: 'failed',
      errorKey: 'error.server_error',
      retryable: true,
    })

    const retried = retryItem(failed, 2)

    expect(retried[1]).toMatchObject({ status: 'waiting', errorKey: null })
    expect(retryItem(base, 1)[0].status).toBe('waiting') // 失敗していない写真は、変わらない
  })

  it('送り直せない写真は、戻らない', () => {
    const { items } = addFiles([], [file('application/pdf')], 1)

    expect(retryItem(items, 1)[0].status).toBe('failed')
  })

  it('写真を外せる', () => {
    expect(removeItem(base, 2).map((item) => item.id)).toEqual([1, 3])
  })

  it('載せた枚数と、全部の枚数を数える', () => {
    const mixed = updateItem(updateItem(base, 1, { status: 'done' }), 3, { status: 'failed' })

    expect(progress(mixed)).toEqual({ done: 1, total: 3 })
  })
})

describe('canSend', () => {
  const waiting = addFiles([], files(2), 1).items

  it('待ちの写真があるときだけ、送れる', () => {
    expect(canSend([])).toBe(false)
    expect(canSend(waiting)).toBe(true)
    expect(canSend(waiting.map((item) => ({ ...item, status: 'done' as const })))).toBe(false)
  })

  it('いま送っている写真があるときは、送れない（二重に送らない）', () => {
    expect(canSend(updateItem(waiting, 1, { status: 'sending' }))).toBe(false)
  })

  it('コメントが長すぎる写真があるときは、送れない', () => {
    expect(canSend(updateItem(waiting, 1, { comment: 'あ'.repeat(101) }))).toBe(false)
    expect(canSend(updateItem(waiting, 1, { comment: 'あ'.repeat(100) }))).toBe(true)
  })
})

describe('commentTooLong', () => {
  it('100 文字までは、よい。絵文字も 1 文字と数える', () => {
    expect(commentTooLong('あ'.repeat(100))).toBe(false)
    expect(commentTooLong('😀'.repeat(100))).toBe(false)
    expect(commentTooLong('あ'.repeat(101))).toBe(true)
  })
})

describe('errorKeyFor', () => {
  it('invalid_file は、PDF を含まない専用の文言にする', () => {
    expect(errorKeyFor(new ApiError(422, 'invalid_file', 'error.invalid_file'))).toBe(
      'album_upload.invalid_file',
    )
  })

  it('validation_error は、コメントが長すぎる案内にする', () => {
    expect(errorKeyFor(new ApiError(422, 'validation_error', 'error.validation_error'))).toBe(
      'album_upload.validation_error',
    )
  })

  it('ほかのエラーは、辞書のキーをそのまま使う。API 以外の失敗は server_error', () => {
    expect(errorKeyFor(new ApiError(403, 'forbidden', 'error.forbidden'))).toBe('error.forbidden')
    expect(errorKeyFor(new Error('x'))).toBe('error.server_error')
  })
})
