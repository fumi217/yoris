import { useTranslation } from 'react-i18next'
import { Icon } from '../../components/Icon'
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
    <section className="space-y-3">
      <h2 className="text-lg font-bold">
        <Text k="album_upload.posted_title" />
      </h2>
      {album && !album.family_visible && (
        <p className="rounded border-2 border-amber-600 bg-amber-50 p-2 font-bold">
          <Icon name="warning" className="mr-1" />
          <Text k="album_upload.family_hidden" />
        </p>
      )}
      {/* 知らせは、読み上げにも伝わるように、先に場所を用意しておく */}
      <p role="status" className="font-bold">
        {noticeKey && <Text k={noticeKey} />}
      </p>
      {deleteErrorKey && (
        <p role="alert" className="text-red-800">
          <Text k={deleteErrorKey} />
        </p>
      )}
      {!album && loadErrorKey && (
        <p role="alert" className="text-red-800">
          <Text k={loadErrorKey} />
        </p>
      )}
      {album && album.photos.length === 0 && (
        <p className="text-gray-600">
          <Text k="album_upload.posted_empty" />
        </p>
      )}
      {album && album.photos.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {album.photos.map((photo) => (
            <li key={photo.id} className="space-y-1">
              <img
                src={photo.url}
                alt=""
                loading="lazy"
                decoding="async"
                className="aspect-square w-full rounded bg-gray-100 object-cover"
              />
              {/* 「削除する」が、どの写真のものか読み上げで分かるように、ボタンにつなぐ説明。
                  コメントがあればそれを、なければ載せた日時を使う（画面には出さない） */}
              {photo.comment ? (
                // 職員が書いた文。辞書を通さず、文字としてだけ出す
                <p id={`album-photo-${photo.id}-desc`} className="text-sm break-words">
                  {photo.comment}
                </p>
              ) : (
                <p id={`album-photo-${photo.id}-desc`} className="sr-only">
                  <Ruby text={t('album_upload.posted_at', postedAtParts(photo.posted_at))} />
                </p>
              )}
              <ConfirmButton
                describedBy={`album-photo-${photo.id}-desc`}
                labelKey="album_upload.delete"
                confirmKey="album_upload.delete_confirm"
                busyKey="album_upload.deleting"
                busy={deletingId === photo.id}
                disabled={deletingId !== null}
                onConfirm={() => onDelete(photo.id)}
                className="min-h-12 text-sm text-gray-700 underline"
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
