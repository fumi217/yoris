import { useInfiniteQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, messageKeyOf } from '../../api/client'
import { EmptyState } from '../../components/EmptyState'
import { Icon } from '../../components/Icon'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import { weekdayOf } from './contactBookView'
import { todayInJapan } from './visits/visitDates'
import {
  dayKindOf,
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
  const { t, i18n } = useTranslation()
  // 大きく見る写真（その日の日付も持つ。大きく見る画面の日付の表示に使う）
  const [selected, setSelected] = useState<(AlbumPhoto & { dayDate?: string }) | null>(null)

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
    <section className="space-y-5 p-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold">
          <Text k="album.title" />
        </h1>
        <p className="text-ink-sub">
          <Text k="album.subtitle" />
        </p>
      </div>
      {days.length === 0 ? (
        <div className="rounded-2xl border border-card-line bg-card">
          <EmptyState
            icon="album"
            title={<Text k="album.empty" />}
            description={<Text k="album.empty_sub" />}
          />
        </div>
      ) : (
        days.map((day) => (
          <section key={day.date} className="space-y-2">
            <div className="mx-1 flex items-center justify-between gap-3">
              <h2 className="text-sm font-bold">
                <Ruby text={dayHeading(t, i18n.language, day.date)} />
              </h2>
              <span className="rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-bold text-primary-dark">
                <Ruby text={t('album.count', { count: day.photos.length })} />
              </span>
            </div>
            <ul className="grid grid-cols-3 gap-2 rounded-2xl border border-card-line bg-card p-2.5">
              {day.photos.map((photo) => (
                <li key={photo.id} className="space-y-1">
                  <button
                    type="button"
                    className="block w-full"
                    aria-label={stripRuby(t('album.open'))}
                    onClick={() => setSelected({ ...photo, dayDate: day.date })}
                  >
                    {/* 枠の大きさを先に決める（loading="lazy" が、画面の外の写真までまとめて読み込まないため） */}
                    <img
                      src={photo.url}
                      alt=""
                      loading="lazy"
                      decoding="async"
                      className="aspect-square w-full rounded-xl bg-page object-cover"
                    />
                  </button>
                  {/* 職員が書いた文。辞書を通さず、文字としてだけ出す。2 行まで（大きく見たときは全部） */}
                  {photo.comment && (
                    <p className="line-clamp-2 px-0.5 text-xs break-words">{photo.comment}</p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
      {hasMore && (
        <button
          type="button"
          className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-field-line bg-white px-3 font-bold text-ink shadow-sm disabled:opacity-40"
          disabled={loadingMore}
          onClick={onMore}
        >
          <Text k="album.more" />
          <Icon name="expand" />
        </button>
      )}
      {selected && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={stripRuby(t('album.open'))}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-black/90 p-4"
          // 写真・コメント・ボタンの外側（黒い部分）を押したときも、閉じる（PR #413 ようこさん）
          onClick={(event) => {
            if (event.target === event.currentTarget) setSelected(null)
          }}
        >
          {/* 閉じるボタンは、右上（丸い ×）と下の両方。Esc でも閉じる */}
          {/* 右上の × は、下の「閉じる」と同じ動き。読み上げ・キーボードでは、下のボタンだけを使う
              （同じ名前のボタンが 2 つ並ばないように。指で押しやすい位置に、もう 1 つ置いている） */}
          <button
            type="button"
            aria-hidden="true"
            tabIndex={-1}
            className="absolute top-4 right-4 flex size-11 items-center justify-center rounded-full bg-white/20 text-xl text-white"
            onClick={() => setSelected(null)}
          >
            <Icon name="close" />
          </button>
          <img
            src={selected.url}
            alt=""
            className="max-h-[70vh] max-w-full rounded-2xl object-contain shadow-2xl"
          />
          {selected.comment && (
            <div className="w-full max-w-md rounded-xl bg-white/15 px-3 py-2 text-center text-white">
              <p className="text-xs text-white/80">
                <Ruby text={dayHeading(t, i18n.language, selected.dayDate ?? '')} />
              </p>
              <p className="break-words whitespace-pre-wrap">{selected.comment}</p>
            </div>
          )}
          <button
            type="button"
            className="min-h-12 rounded-xl bg-white px-8 font-bold text-ink shadow-md"
            onClick={() => setSelected(null)}
          >
            <Text k="album.close" />
          </button>
        </div>
      )}
    </section>
  )
}

/** 日の見出し：「今日（10月30日）」「昨日（10月29日）」「10月27日（火）」。日付は日本時間のまま使う。 */
function dayHeading(
  t: (key: string, options?: Record<string, unknown>) => string,
  language: string,
  date: string,
): string {
  if (!date) return ''
  const parts = dayParts(date)
  return t(`album.day_${dayKindOf(date, todayInJapan())}`, {
    ...parts,
    weekday: weekdayOf(date, language),
  })
}
