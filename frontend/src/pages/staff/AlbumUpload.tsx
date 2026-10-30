import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { AlbumPosted, type StaffAlbum } from './AlbumPosted'
import {
  ACCEPT,
  MAX_COMMENT,
  MAX_PHOTOS,
  addFiles,
  canSend,
  deletePhoto,
  errorKeyFor,
  nextToSend,
  progress,
  removeItem,
  retryItem,
  updateItem,
  type UploadItem,
  type UploadStatus,
} from './albumUploadLogic'
import type { StaffContactBook } from './recordValues'

type Resident = StaffContactBook['resident']

const postedKey = (residentId: string) => ['staff', 'album', residentId] as const

const STATUS_MARK: Record<UploadStatus, string> = {
  waiting: '🕒',
  sending: '📤',
  done: '✔',
  failed: '⚠',
}

/**
 * 写真を載せる画面（UI-S10。spec 005 の 005-T014）。`/staff/residents/:residentId/album`
 *
 * 「📷 撮る」と「🖼 写真から選ぶ」（10 枚まで）で選び、写真ごとに一言コメント（任意・100 文字まで）を
 * 付けて、1 枚ずつ順に送る（途中で通信が切れても、切れた分だけ送り直せる。R-01）。
 * 成功・失敗は、色だけでなく、印と文字で出す。失敗した写真だけ「もう一度送る」。
 * 10MB を超える写真・形式が違う写真は、送る前に断る（サーバーでも断る。FR-003）。
 * 文章の入力は求めない（コメントは任意）。
 */
export function AlbumUpload() {
  const { residentId = '' } = useParams()
  const [items, setItems] = useState<UploadItem[]>([])
  const [previews, setPreviews] = useState<Record<number, string>>({})
  const [skipped, setSkipped] = useState(0)
  const [sending, setSending] = useState(false)
  // 送っている途中でも、最新の一覧を読めるように（state は、次の描画まで変わらないため）
  const itemsRef = useRef<UploadItem[]>([])
  const nextId = useRef(1)
  const urls = useRef(new Map<number, string>())

  // 入居者の呼び名・居室（記録の画面で読んだものがあれば、それを使う）
  const book = useQuery({
    queryKey: ['staff', 'contact-book', residentId, 'today'],
    queryFn: () => api.get<StaffContactBook>(`/api/staff/residents/${residentId}/contact-book`),
  })

  // 載せた写真の一覧（削除のボタンもここ）
  const queryClient = useQueryClient()
  const fetchPosted = () => api.get<StaffAlbum>(`/api/staff/residents/${residentId}/album`)
  const posted = useQuery({ queryKey: postedKey(residentId), queryFn: fetchPosted })
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [noticeKey, setNoticeKey] = useState<string | null>(null)
  const [deleteErrorKey, setDeleteErrorKey] = useState<string | null>(null)

  const commit = (next: UploadItem[]) => {
    itemsRef.current = next
    setItems(next)
  }

  // 画面を閉じるときに、プレビュー用の URL を解放する（メモリを使い続けないため）
  useEffect(() => {
    const held = urls.current
    return () => {
      held.forEach((url) => URL.revokeObjectURL(url))
      held.clear()
    }
  }, [])

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    // 同じ写真を、続けて選び直せるように、選んだあとで空にする
    event.target.value = ''
    const added = addFiles(itemsRef.current, files, nextId.current)
    nextId.current = added.nextId
    const fresh: Record<number, string> = {}
    for (const item of added.items) {
      if (!urls.current.has(item.id)) {
        const url = URL.createObjectURL(item.file)
        urls.current.set(item.id, url)
        fresh[item.id] = url
      }
    }
    setPreviews((current) => ({ ...current, ...fresh }))
    setSkipped(added.skipped)
    commit(added.items)
  }

  const onRemove = (id: number) => {
    const url = urls.current.get(id)
    if (url) URL.revokeObjectURL(url)
    urls.current.delete(id)
    setPreviews((current) =>
      Object.fromEntries(Object.entries(current).filter(([key]) => Number(key) !== id)),
    )
    commit(removeItem(itemsRef.current, id))
  }

  // 1 枚ずつ順に送る。失敗しても、次の写真は送る
  const onSend = async () => {
    setSending(true)
    setNoticeKey(null)
    for (let item = nextToSend(itemsRef.current); item; item = nextToSend(itemsRef.current)) {
      commit(updateItem(itemsRef.current, item.id, { status: 'sending' }))
      const form = new FormData()
      form.append('file', item.file)
      if (item.comment.trim() !== '') form.append('comment', item.comment.trim())
      try {
        await api.postForm(`/api/staff/residents/${residentId}/album`, form)
        commit(updateItem(itemsRef.current, item.id, { status: 'done', errorKey: null }))
      } catch (error) {
        commit(
          updateItem(itemsRef.current, item.id, {
            status: 'failed',
            errorKey: errorKeyFor(error),
            retryable: true,
          }),
        )
      }
    }
    setSending(false)
    // 載せた写真が、すぐ下の一覧に出るように
    void queryClient.invalidateQueries({ queryKey: postedKey(residentId) })
  }

  const onDelete = async (id: number) => {
    setDeletingId(id)
    setNoticeKey(null)
    setDeleteErrorKey(null)
    try {
      const outcome = await deletePhoto(
        id,
        () =>
          queryClient.fetchQuery({
            queryKey: postedKey(residentId),
            queryFn: fetchPosted,
            staleTime: 0,
          }),
        (photoId) => api.delete(`/api/staff/album/${photoId}`),
      )
      setNoticeKey(`album_upload.${outcome}`)
      // 消した写真が、一覧から消えるように
      void queryClient.invalidateQueries({ queryKey: postedKey(residentId) })
    } catch (error) {
      // 写真は一覧に残す。もう一度押せる
      setDeleteErrorKey(messageKeyOf(error))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <AlbumUploadView
      residentId={residentId}
      resident={book.data?.resident ?? null}
      items={items}
      previews={previews}
      skipped={skipped}
      sending={sending}
      onPick={onPick}
      onComment={(id, comment) => commit(updateItem(itemsRef.current, id, { comment }))}
      onRemove={onRemove}
      onRetry={(id) => commit(retryItem(itemsRef.current, id))}
      onSend={() => void onSend()}
      posted={
        <AlbumPosted
          album={posted.data}
          loadErrorKey={posted.isError ? messageKeyOf(posted.error) : null}
          deletingId={deletingId}
          noticeKey={noticeKey}
          deleteErrorKey={deleteErrorKey}
          onDelete={(id) => void onDelete(id)}
        />
      }
    />
  )
}

type ViewProps = {
  residentId: string
  resident: Resident | null
  items: UploadItem[]
  previews: Record<number, string>
  skipped: number
  sending: boolean
  onPick: (event: ChangeEvent<HTMLInputElement>) => void
  onComment: (id: number, comment: string) => void
  onRemove: (id: number) => void
  onRetry: (id: number) => void
  onSend: () => void
  // 載せた写真の一覧（AlbumPosted）。テストでは、載せる部分だけを出すので、なくてもよい
  posted?: ReactNode
}

const pickClass =
  'flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded border-2 border-primary px-4 font-bold text-primary-dark'

/** 画面の中身（テストではこれを直接出す）。 */
export function AlbumUploadView({
  residentId,
  resident,
  items,
  previews,
  skipped,
  sending,
  onPick,
  onComment,
  onRemove,
  onRetry,
  onSend,
  posted,
}: ViewProps) {
  const { t } = useTranslation()
  const { done, total } = progress(items)

  return (
    <section className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        <Text k="album_upload.title" />
        {resident && (
          <span className="ml-3 text-base font-normal">
            <span className="mr-2 text-gray-600">{resident.room}</span>
            {/* 入居者の呼び名は、辞書を通さずそのまま出す */}
            {resident.display_name}
          </span>
        )}
      </h1>

      <div className="grid grid-cols-2 gap-3">
        {/* 端末のカメラを開く（capture）。複数枚は選べないので、「選ぶ」と分ける（R-01） */}
        <label className={pickClass}>
          <span aria-hidden="true">📷</span>
          <Text k="album_upload.take" />
          <input
            type="file"
            accept={ACCEPT}
            capture="environment"
            className="sr-only"
            onChange={onPick}
          />
        </label>
        <label className={pickClass}>
          <span aria-hidden="true">🖼</span>
          <Text k="album_upload.choose" />
          <input type="file" accept={ACCEPT} multiple className="sr-only" onChange={onPick} />
        </label>
      </div>
      <p className="text-sm text-gray-600">
        <Ruby text={t('album_upload.hint', { max: MAX_PHOTOS })} />
      </p>
      {skipped > 0 && (
        <p role="alert" className="font-bold text-red-800">
          ⚠ <Ruby text={t('album_upload.over_limit', { max: MAX_PHOTOS, skipped })} />
        </p>
      )}

      {items.length > 0 && (
        <>
          <ul className="space-y-3">
            {items.map((item) => (
              <li key={item.id} className="flex gap-3 rounded border border-card-line p-3">
                {item.file.type.startsWith('image/') ? (
                  <img
                    src={previews[item.id]}
                    alt=""
                    className="aspect-square h-24 w-24 shrink-0 rounded bg-gray-100 object-cover"
                  />
                ) : (
                  // 画像でないファイル（PDF など）は、プレビューできない。壊れた画像の印を出さない
                  <div
                    aria-hidden="true"
                    className="flex h-24 w-24 shrink-0 items-center justify-center rounded bg-gray-100 text-3xl"
                  >
                    📄
                  </div>
                )}
                <div className="min-w-0 flex-1 space-y-2">
                  {/* 状態は、印と文字で出す（色だけに頼らない） */}
                  <p className="font-bold">
                    <span aria-hidden="true" className="mr-1">
                      {STATUS_MARK[item.status]}
                    </span>
                    <Text k={`album_upload.status.${item.status}`} />
                  </p>
                  {item.errorKey && (
                    <p role="alert" className="text-red-800">
                      <Text k={item.errorKey} />
                    </p>
                  )}
                  {item.status !== 'done' && item.retryable && (
                    <label className="block text-sm">
                      <Ruby text={t('album_upload.comment', { max: MAX_COMMENT })} />
                      <input
                        type="text"
                        maxLength={MAX_COMMENT}
                        value={item.comment}
                        disabled={item.status === 'sending'}
                        className="mt-1 block w-full rounded border-2 border-field-line p-2"
                        onChange={(event) => onComment(item.id, event.target.value)}
                      />
                    </label>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {item.status === 'failed' && item.retryable && (
                      <button
                        type="button"
                        className="min-h-12 rounded border-2 border-primary px-4 font-bold text-primary-dark"
                        onClick={() => onRetry(item.id)}
                      >
                        <Text k="album_upload.retry" />
                      </button>
                    )}
                    {(item.status === 'waiting' || item.status === 'failed') && (
                      <button
                        type="button"
                        className="min-h-12 rounded border-2 border-field-line px-4"
                        onClick={() => onRemove(item.id)}
                      >
                        <Text k="album_upload.remove" />
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          <p aria-live="polite" className="font-bold">
            <Ruby text={t('album_upload.progress', { done, total })} />
          </p>
          <button
            type="button"
            className="min-h-12 w-full rounded bg-primary px-4 font-bold text-white disabled:opacity-60"
            disabled={!canSend(items) || sending}
            onClick={onSend}
          >
            <Text k="album_upload.send" />
          </button>
        </>
      )}

      {posted}

      <p>
        <Link to={`/staff/residents/${residentId}`} className="text-primary underline">
          <Text k="album_upload.back" />
        </Link>
      </p>
    </section>
  )
}
