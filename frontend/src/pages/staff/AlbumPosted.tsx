import { useTranslation } from 'react-i18next'
import { ConfirmButton } from '../../components/ConfirmButton'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { postedAtParts } from './albumUploadLogic'

/** GET /api/staff/residents/{id}/album の返り値。 */
export type PostedPhoto = { id: number; posted_at: string; comment: string | null; url: string }
export type StaffAlbum = { family_visible: boolean; photos: PostedPhoto[] }

type Props = {
  album: StaffAlbum | undefined
  // 一覧を読めなかったときの文言のキー（まだ 1 枚も読めていないときだけ出す）
  loadErrorKey: string | null
  deletingId: number | null
  // 削除の結果の知らせ（album_upload.deleted／album_upload.already_deleted）
  noticeKey: string | null
  deleteErrorKey: string | null
  onDelete: (id: number) => void
}

/**
 * 載せた写真の一覧と、削除のボタン（005-T020。FR-011・FR-016）。
 * 家族に見せていない設定のときは、載せられるが家族には見えないことを知らせる。
 * 削除は 2 回押して決める（ConfirmButton）。写真は家族の画面と同じ見せ方
 * （枠の大きさを先に決め、画面に出るときに読む。サムネイルは作らない）。
 */
export function AlbumPosted({
  album,
  loadErrorKey,
  deletingId,
  noticeKey,
  deleteErrorKey,
  onDelete,
}: Props) {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="album-posted">
      <h2
        id="album-posted"
        className="flex items-baseline justify-between border-b border-card-line pb-1 font-bold"
      >
        <span>
          <Text k="album_upload.posted_title" />
        </span>
        {album && album.photos.length > 0 && (
          <span className="text-sm font-normal text-ink-sub">
            <Ruby text={t('album_upload.count', { count: album.photos.length })} />
          </span>
        )}
      </h2>
      {album && !album.family_visible && (
        <p className="mt-3 font-bold text-amber-800">
          <Text k="album_upload.family_hidden" />
        </p>
      )}
      {/* 知らせは、読み上げにも伝わるように、先に場所を用意しておく */}
      <p role="status" className="mt-3 font-bold empty:hidden">
        {noticeKey && <Text k={noticeKey} />}
      </p>
      {deleteErrorKey && (
        <p role="alert" className="mt-3 text-red-800">
          <Text k={deleteErrorKey} />
        </p>
      )}
      {!album && loadErrorKey && (
        <p role="alert" className="mt-3 text-red-800">
          <Text k={loadErrorKey} />
        </p>
      )}
      {album && album.photos.length === 0 && (
        <p className="mt-3 text-ink-sub">
          <Text k="album_upload.posted_empty" />
        </p>
      )}
      {album && album.photos.length > 0 && (
        <ul>
          {album.photos.map((photo) => (
            <li
              key={photo.id}
              className="grid grid-cols-[72px_1fr] gap-3.5 border-b border-card-line py-3.5 min-[420px]:grid-cols-[80px_1fr]"
            >
              <img
                src={photo.url}
                alt=""
                loading="lazy"
                decoding="async"
                className="aspect-square w-full rounded-md bg-card object-cover"
              />
              <div className="flex min-w-0 flex-col gap-1">
                {/* 「削除する」が、どの写真のものか読み上げで分かるように、ボタンにつなぐ説明。
                    コメントがあればそれを、なければ載せた日時を使う */}
                {photo.comment ? (
                  // 職員が書いた文。辞書を通さず、文字としてだけ出す
                  <p id={`album-photo-${photo.id}-desc`} className="leading-relaxed break-words">
                    {photo.comment}
                  </p>
                ) : (
                  <p id={`album-photo-${photo.id}-desc`} className="sr-only">
                    <Ruby text={t('album_upload.posted_at', postedAtParts(photo.posted_at))} />
                  </p>
                )}
                <p className="text-sm text-ink-sub tabular-nums">
                  {postedAtLabel(photo.posted_at)}
                </p>
                <ConfirmButton
                  describedBy={`album-photo-${photo.id}-desc`}
                  labelKey="album_upload.delete"
                  confirmKey="album_upload.delete_confirm"
                  busyKey="album_upload.deleting"
                  busy={deletingId === photo.id}
                  disabled={deletingId !== null}
                  onConfirm={() => onDelete(photo.id)}
                  className="min-h-11 self-start text-sm text-ink-sub underline"
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** 載せた日時（"11/3 14:20"）。 */
function postedAtLabel(iso: string): string {
  const parts = postedAtParts(iso)
  return `${parts.month}/${parts.day} ${parts.time}`
}
