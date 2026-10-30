import { useInfiniteQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import {
  dayParts,
  mergeAlbumPages,
  nextBefore,
  type AlbumDay,
  type AlbumPage,
  type AlbumPhoto,
} from './albumView'

const ALBUM_KEY = ['family', 'album'] as const

/**
 * 家族のアルバム（UI-F06。spec 005 の 005-T012）。`/family/album`
 * 自分の入居者の写真を、載せた日（日本時間）ごとに、新しい日を上にして並べる。
 * 写真は元の写真を、枠の大きさを先に決めて（正方形）小さく並べ、画面に出るときに読む
 * （サムネイルは作らない）。タップで大きく出す。続きは「もっと見る」（最初は API が決めた 12 枚）。
 * アルバムを見せない設定のときは、API が 404 を返す（エラーの文言を出す）。
 */
export function Album() {
  const album = useInfiniteQuery({
    queryKey: ALBUM_KEY,
    queryFn: ({ pageParam }) =>
      api.get<AlbumPage>(`/api/family/album${pageParam ? `?before=${pageParam}` : ''}`),
    initialPageParam: 0,
    getNextPageParam: nextBefore,
  })

  // 写真がまだ 1 枚もない（読み込み中・最初の読み込みの失敗）ときだけ、文だけを出す。
  // 「もっと見る」や読み直しが失敗しても isError は真になるので、データがあれば一覧を残す
  if (!album.data) {
    return <Message k={album.isError ? messageKeyOf(album.error) : 'layout.loading'} />
  }
  return (
    <>
      <AlbumView
        days={mergeAlbumPages(album.data.pages)}
        hasMore={album.hasNextPage}
        loadingMore={album.isFetchingNextPage}
        onMore={() => void album.fetchNextPage()}
      />
      {album.isError && <Message k={messageKeyOf(album.error)} />}
    </>
  )
}

type ViewProps = {
  days: AlbumDay[]
  hasMore: boolean
  loadingMore: boolean
  onMore: () => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function AlbumView({ days, hasMore, loadingMore, onMore }: ViewProps) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<AlbumPhoto | null>(null)

  // 大きく出しているあいだ、Esc キーで閉じられる
  useEffect(() => {
    if (!selected) return
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSelected(null)
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [selected])

  return (
    <section className="space-y-6 p-4">
      <h1 className="text-xl font-bold">
        <Text k="album.title" />
      </h1>
      {days.length === 0 ? (
        <p className="text-gray-600">
          <Text k="album.empty" />
        </p>
      ) : (
        days.map((day) => (
          <section key={day.date} className="space-y-2">
            <h2 className="font-bold">
              <Ruby text={t('album.day', dayParts(day.date))} />
            </h2>
            <ul className="grid grid-cols-3 gap-2">
              {day.photos.map((photo) => (
                <li key={photo.id} className="space-y-1">
                  <button
                    type="button"
                    className="block w-full"
                    aria-label={stripRuby(t('album.open'))}
                    onClick={() => setSelected(photo)}
                  >
                    {/* 枠の大きさを先に決める（loading="lazy" が、画面の外の写真までまとめて読み込まないため） */}
                    <img
                      src={photo.url}
                      alt=""
                      loading="lazy"
                      decoding="async"
                      className="aspect-square w-full rounded bg-gray-100 object-cover"
                    />
                  </button>
                  {/* 職員が書いた文。辞書を通さず、文字としてだけ出す */}
                  {photo.comment && <p className="text-sm break-words">{photo.comment}</p>}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
      {hasMore && (
        <button
          type="button"
          className="min-h-12 w-full rounded border-2 border-field-line px-3 disabled:opacity-40"
          disabled={loadingMore}
          onClick={onMore}
        >
          <Text k="album.more" />
        </button>
      )}
      {selected && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={stripRuby(t('album.open'))}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-3 bg-black/85 p-4"
        >
          <img src={selected.url} alt="" className="max-h-[75vh] max-w-full object-contain" />
          {selected.comment && (
            <p className="max-w-full text-center break-words text-white">{selected.comment}</p>
          )}
          <button
            type="button"
            className="min-h-12 rounded bg-white px-6 font-bold"
            onClick={() => setSelected(null)}
          >
            <Text k="album.close" />
          </button>
        </div>
      )}
    </section>
  )
}
