import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { themeIconName } from '../../components/themeIcon'
import { Icon } from '../../components/Icon'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentName } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import { recordLabelKey, shiftDate, timeInJapan, timeline } from './contactBookTimeline'
import type { StaffContactBook as Book, StaffReply } from './recordValues'
import { ReplyEditor } from './ReplyEditor'
import { replyBody } from './replyForm'
import { monthDay } from './residentRows'

/**
 * 職員の連絡帳の見返し（UI-S04。spec 001 の T033・FR-024）。`/staff/residents/:residentId/contact-book?date=`
 * 入居者 × 日付ごとに、その日の記録と返事を時刻の順に出す（事務所で介護記録を書くための一次メモ）。
 * 職員向けなので、家族に見せない項目も出す（R-06）。日付を省くと今日（日本時間）。
 * 今日の返事は「直す」から、その場で直せる（001-T063。お知らせは作り直さない）。
 */
export function StaffContactBook() {
  const { residentId = '' } = useParams()
  const [params] = useSearchParams()
  const date = params.get('date')
  const queryClient = useQueryClient()

  const book = useQuery({
    queryKey: ['staff', 'contact-book', residentId, date ?? 'today'],
    queryFn: () =>
      api.get<Book>(
        `/api/staff/residents/${residentId}/contact-book${date ? `?date=${encodeURIComponent(date)}` : ''}`,
      ),
  })

  const edit = useMutation({
    mutationFn: ({ id, templateIds, note }: { id: number; templateIds: number[]; note: string }) =>
      api.patch(`/api/staff/replies/${id}`, replyBody(templateIds, note)),
    // 見返し（どの日付でも）と、記録の画面の今日の分を読み直す
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['staff', 'contact-book', residentId] }),
  })

  if (book.isPending) return <Message k="layout.loading" />
  if (book.isError) return <Message k={messageKeyOf(book.error)} />
  return (
    <ContactBookView
      book={book.data}
      savingReplyId={edit.isPending ? edit.variables.id : null}
      editErrorKey={edit.isError ? messageKeyOf(edit.error) : null}
      onEditReply={(id, templateIds, note, done) =>
        edit.mutate({ id, templateIds, note }, { onSuccess: done })
      }
      onStartEdit={() => edit.reset()}
    />
  )
}

type ViewProps = {
  book: Book
  // 返事を直しているときの値（001-T063）
  savingReplyId?: number | null
  editErrorKey?: string | null
  onEditReply?: (id: number, templateIds: number[], note: string, done: () => void) => void
  onStartEdit?: () => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function ContactBookView({
  book,
  savingReplyId = null,
  editErrorKey = null,
  onEditReply,
  onStartEdit,
}: ViewProps) {
  const { t } = useTranslation()
  const base = `/staff/residents/${book.resident.id}`
  const entries = timeline(book)

  return (
    <section className="space-y-4 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-bold">
          <Text k="staff_contact_book.title" />
          <span className="ml-3 text-base font-normal">
            <span className="mr-2 text-gray-600">{book.resident.room}</span>
            <ResidentName
              name={book.resident.display_name}
              ruby={book.resident.display_name_ruby}
            />
          </span>
        </h1>
        <nav className="flex items-center gap-3 text-sm">
          <Link
            to={`${base}/contact-book?date=${shiftDate(book.date, -1)}`}
            className="text-primary underline"
          >
            <Icon name="prev" className="mr-1" />
            <Text k="staff_contact_book.previous" />
          </Link>
          <span className="font-bold">
            <Ruby text={t('staff_contact_book.date', monthDay(book.date))} />
          </span>
          <Link
            to={`${base}/contact-book?date=${shiftDate(book.date, 1)}`}
            className="text-primary underline"
          >
            <Text k="staff_contact_book.next" />
            <Icon name="next" className="ml-1" />
          </Link>
        </nav>
      </div>
      <p className="text-xs text-gray-600">
        <Text k="staff_contact_book.note" />
      </p>

      {entries.length === 0 ? (
        <Message k="staff_contact_book.empty" />
      ) : (
        <ol className="divide-y border-y">
          {entries.map((entry) => (
            <li
              key={`${entry.kind}-${entry.kind === 'record' ? entry.record.id : entry.reply.id}`}
              className="flex gap-4 py-3"
            >
              <time dateTime={entry.at} className="w-12 shrink-0 text-gray-600">
                {timeInJapan(entry.at)}
              </time>
              {entry.kind === 'record' ? (
                <div className="flex flex-1 flex-wrap justify-between gap-2">
                  <span>
                    <span className="mr-2 font-bold">
                      <Text k={recordLabelKey(entry.record)} />
                    </span>
                    <Text k={`record.value.${entry.record.item}.${entry.record.value}`} />
                  </span>
                  <span className="text-sm text-gray-600">{entry.record.recorded_by_name}</span>
                </div>
              ) : (
                <div className="flex-1 space-y-1">
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="font-bold">
                      <Icon
                        name={themeIconName(entry.reply.theme_code)}
                        className="mr-2 text-primary"
                      />
                      <Ruby
                        text={t('staff_contact_book.reply', { theme: t(entry.reply.theme_code) })}
                      />
                      {entry.reply.edited && <Text k="staff_contact_book.edited" />}
                    </span>
                    <span className="text-sm text-gray-600">{entry.reply.replied_by_name}</span>
                  </div>
                  <ul className="list-inside list-disc">
                    {entry.reply.template_codes.map((code) => (
                      <li key={code}>
                        <Text k={code} />
                      </li>
                    ))}
                  </ul>
                  {/* 職員が書き足した文は、辞書を通さず文字としてだけ出す */}
                  {entry.reply.note && <p className="whitespace-pre-wrap">{entry.reply.note}</p>}
                  <p className="text-xs text-gray-600">
                    <Text
                      k={entry.reply.read ? 'staff_contact_book.read' : 'staff_contact_book.unread'}
                    />
                  </p>
                  {entry.reply.editable && onEditReply && (
                    <EditReply
                      reply={entry.reply}
                      saving={savingReplyId === entry.reply.id}
                      errorKey={editErrorKey}
                      onEditReply={onEditReply}
                      onStartEdit={onStartEdit}
                    />
                  )}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      <Link to={base} className="inline-block text-primary underline">
        <Text k="staff_contact_book.back" />
      </Link>
    </section>
  )
}

type EditReplyProps = {
  reply: StaffReply
  saving: boolean
  errorKey: string | null
  onEditReply: (id: number, templateIds: number[], note: string, done: () => void) => void
  onStartEdit?: () => void
}

/** 「この返事を直す」と、押したときに出る直す欄。 */
function EditReply({ reply, saving, errorKey, onEditReply, onStartEdit }: EditReplyProps) {
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => {
          onStartEdit?.()
          setOpen(true)
        }}
        className="text-sm text-primary underline"
      >
        <Text k="staff_contact_book.edit" />
      </button>
    )
  }
  return (
    <ReplyEditor
      reply={reply}
      saving={saving}
      errorKey={errorKey}
      onSave={(templateIds, note) => onEditReply(reply.id, templateIds, note, () => setOpen(false))}
      onClose={() => setOpen(false)}
    />
  )
}
