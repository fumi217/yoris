import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Icon } from '../../components/Icon'
import { useEffect, useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Text } from '../../components/Text'
import { ResidentName } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
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
} from './albumUploadLogic'
import type { StaffContactBook } from './recordValues'

type Resident = StaffContactBook['resident']

const postedKey = (residentId: string) => ['staff', 'album', residentId] as const

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

// 「撮る」「写真から選ぶ」：青い細い枠線の白いボタン（押せると分かるように。#461）
const pickClass =
  'inline-flex min-h-12 cursor-pointer items-center rounded-xl border border-primary bg-card px-4 text-[17px] font-bold text-primary-dark'

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
    // 見た目（#461）：カード・影・丸いラベル・状態の印を使わず、細い線と余白と文字だけで区切る。
    // 色が付くのは「送る」と、失敗の赤い文字だけ（状態は、文字で言い分ける）
    <section className="space-y-6 p-4">
      <div>
        <Link
          to={`/staff/residents/${residentId}`}
          className="-mb-1 inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-primary"
        >
          <Icon name="prev" />
          <Text k="album_upload.back" />
        </Link>
        {resident && (
          <>
            <p className="mt-1 text-sm text-ink-sub">
              <Ruby text={t('album_upload.room', { room: resident.room })} />
            </p>
            <p className="text-2xl font-extrabold">
              <ResidentName name={resident.display_name} ruby={resident.display_name_ruby} />
            </p>
          </>
        )}
        <h1 className={resident ? 'mt-1 text-ink-sub' : 'text-2xl font-bold'}>
          <Text k="album_upload.title" />
        </h1>
      </div>

      <div>
        <div className="flex flex-wrap gap-3">
          {/* 端末のカメラを開く（capture）。複数枚は選べないので、「選ぶ」と分ける（R-01） */}
          <label className={pickClass}>
            <span>
              <Text k="album_upload.take" />
            </span>
            <input
              type="file"
              accept={ACCEPT}
              capture="environment"
              className="sr-only"
              onChange={onPick}
            />
          </label>
          <label className={pickClass}>
            <span>
              <Text k="album_upload.choose" />
            </span>
            <input type="file" accept={ACCEPT} multiple className="sr-only" onChange={onPick} />
          </label>
        </div>
        <p className="mt-2 text-sm text-ink-sub">
          <Ruby text={t('album_upload.hint', { max: MAX_PHOTOS })} />
        </p>
        {skipped > 0 && (
          <p role="alert" className="mt-2 font-bold text-red-800">
            <Ruby text={t('album_upload.over_limit', { max: MAX_PHOTOS, skipped })} />
          </p>
        )}
      </div>

      {items.length > 0 && (
        <section aria-labelledby="album-selected">
          <h2
            id="album-selected"
            className="flex items-baseline justify-between border-b border-card-line pb-1 font-bold"
          >
            <span>
              <Text k="album_upload.selected_title" />
            </span>
            <span className="text-sm font-normal text-ink-sub">
              <Ruby text={t('album_upload.count', { count: items.length })} />
            </span>
          </h2>
          <ul>
            {items.map((item) => (
              <li
                key={item.id}
                className="grid grid-cols-[72px_1fr] gap-3.5 border-b border-card-line py-3.5 min-[420px]:grid-cols-[80px_1fr]"
              >
                {item.file.type.startsWith('image/') ? (
                  <img
                    src={previews[item.id]}
                    alt=""
                    className="aspect-square w-full rounded-md bg-card object-cover"
                  />
                ) : (
                  // 画像でないファイル（PDF など）は、プレビューできない。壊れた画像の印を出さない
                  <div
                    aria-hidden="true"
                    className="flex aspect-square w-full items-center justify-center rounded-md bg-card text-3xl text-ink-sub"
                  >
                    <Icon name="file" />
                  </div>
                )}
                <div className="flex min-w-0 flex-col gap-1.5">
                  {/* 状態は、文字で言い分ける（載せました／送っています／待っています／載せられませんでした）。
                      失敗だけ赤い文字（色だけに頼らない。1.4.1） */}
                  <p
                    className={
                      item.status === 'failed'
                        ? 'font-bold text-red-800'
                        : item.status === 'done'
                          ? 'font-bold'
                          : 'text-ink-sub'
                    }
                  >
                    <Text k={`album_upload.status.${item.status}`} />
                  </p>
                  {item.errorKey && (
                    <p role="alert" className="text-sm text-red-800">
                      <Text k={item.errorKey} />
                    </p>
                  )}
                  {item.status !== 'done' && item.retryable && (
                    <label className="block text-sm text-ink-sub">
                      <span className="sr-only">
                        <Ruby text={t('album_upload.comment', { max: MAX_COMMENT })} />
                      </span>
                      <input
                        type="text"
                        maxLength={MAX_COMMENT}
                        value={item.comment}
                        disabled={item.status === 'sending'}
                        placeholder={stripRuby(t('album_upload.comment_placeholder'))}
                        className="block w-full rounded-lg border border-field-line bg-card px-3 py-1.5 text-base text-ink placeholder:text-ink-sub"
                        onChange={(event) => onComment(item.id, event.target.value)}
                      />
                    </label>
                  )}
                  <div className="flex flex-wrap gap-x-4">
                    {item.status === 'failed' && item.retryable && (
                      <button
                        type="button"
                        className="min-h-11 text-sm font-bold text-primary underline"
                        onClick={() => onRetry(item.id)}
                      >
                        <Text k="album_upload.retry" />
                      </button>
                    )}
                    {(item.status === 'waiting' || item.status === 'failed') && (
                      <button
                        type="button"
                        className="min-h-11 text-sm text-ink-sub underline"
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
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-3">
            <p aria-live="polite" className="min-w-0 flex-1 basis-48 text-sm text-ink-sub">
              <Ruby text={t('album_upload.progress', { done, total })} />
            </p>
            <button
              type="button"
              className="min-h-13 w-full rounded-lg bg-primary px-8 text-[17px] font-bold text-white disabled:opacity-60 min-[420px]:w-auto"
              disabled={!canSend(items) || sending}
              onClick={onSend}
            >
              <Text k="album_upload.send" />
            </button>
          </div>
        </section>
      )}

      {posted}
    </section>
  )
}
