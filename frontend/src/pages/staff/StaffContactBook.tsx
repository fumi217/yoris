import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Icon, type IconName } from '../../components/Icon'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentName } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import { shiftDate, timeInJapan, timeline } from './contactBookTimeline'
import type { StaffContactBook as Book, StaffRecord, StaffReply } from './recordValues'
import { ReplyEditor } from './ReplyEditor'
import { replyBody } from './replyForm'
import { MEAL_SLOTS, monthDay } from './residentRows'

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

// 白い面（枠線は使わず、ごく弱い影と余白でまとまりを分ける。#457）
const BLOCK =
  'rounded-[18px] bg-card px-5 py-1.5 shadow-[0_1px_2px_rgb(15_31_61/0.04),0_6px_16px_rgb(15_31_61/0.05)]'

/**
 * 画面の中身（テストではこれを直接出す）。
 * 見た目（#457）：家族の連絡帳と同じ並び（返事 → 食事 → 機嫌・様子／眠り）で、家族からどう見えているかが分かるように。
 * 記録した時刻と人は、右に小さく。まだの欄は「まだ記録されていません」。
 */
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
  const replies = entries.flatMap((entry) => (entry.kind === 'reply' ? [entry.reply] : []))
  const recordOf = (item: string, slot: string) =>
    book.records.find((record) => record.item === item && record.slot === slot) ?? null
  const mealSlots = MEAL_SLOTS.filter((slot) => slot !== 'snack' || recordOf('meal', slot))

  return (
    <section className="space-y-4 p-4">
      <Link
        to={base}
        className="-mb-2 inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-primary"
      >
        <Icon name="prev" />
        <Text k="staff_contact_book.back" />
      </Link>
      <div>
        <p className="text-sm text-ink-sub">
          <Ruby text={t('reply_page.room', { room: book.resident.room })} />
        </p>
        <h1 className="text-2xl font-extrabold">
          <ResidentName name={book.resident.display_name} ruby={book.resident.display_name_ruby} />
          <Text k="staff_contact_book.title_suffix" />
        </h1>
        <p className="mt-1 text-sm text-ink-sub">
          <Text k="staff_contact_book.note" />
        </p>
      </div>

      {/* 前の日・日付・次の日（矢印は、名前を読み上げで伝える） */}
      <nav className="flex items-center justify-between">
        <Link
          to={`${base}/contact-book?date=${shiftDate(book.date, -1)}`}
          aria-label={stripRuby(t('staff_contact_book.previous'))}
          className="flex size-11 items-center justify-center rounded-full text-primary hover:bg-primary-soft"
        >
          <Icon name="prev" />
        </Link>
        <span className="text-lg font-bold">
          <Ruby text={t('staff_contact_book.date', monthDay(book.date))} />
        </span>
        <Link
          to={`${base}/contact-book?date=${shiftDate(book.date, 1)}`}
          aria-label={stripRuby(t('staff_contact_book.next'))}
          className="flex size-11 items-center justify-center rounded-full text-primary hover:bg-primary-soft"
        >
          <Icon name="next" />
        </Link>
      </nav>

      {entries.length === 0 ? (
        <Message k="staff_contact_book.empty" />
      ) : (
        <>
          {replies.length > 0 && (
            <section className={BLOCK} aria-labelledby="staff-book-replies">
              <BlockTitle
                id="staff-book-replies"
                icon="notice-reply"
                titleKey="staff_contact_book.replies_title"
              />
              <ul>
                {replies.map((reply) => (
                  <li key={reply.id} className="border-t border-card-line py-3.5 first:border-t-0">
                    <p className="text-sm text-ink-sub">
                      <Ruby text={t('staff_contact_book.reply', { theme: t(reply.theme_code) })} />
                      {reply.edited && <Text k="staff_contact_book.edited" />}
                    </p>
                    <ul className="mt-1.5 list-disc pl-5 leading-relaxed">
                      {reply.template_codes.map((code) => (
                        <li key={code}>
                          <Text k={code} />
                        </li>
                      ))}
                    </ul>
                    {/* 職員が書き足した文は、辞書を通さず文字としてだけ出す */}
                    {reply.note && (
                      <p className="mt-1 leading-relaxed whitespace-pre-wrap">{reply.note}</p>
                    )}
                    <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-sub">
                      <span className="tabular-nums">
                        {timeInJapan(reply.replied_at)}
                        <span className="ml-2">{reply.replied_by_name}</span>
                      </span>
                      <span className={reply.read ? '' : 'font-bold text-amber-800'}>
                        <Text
                          k={reply.read ? 'staff_contact_book.read' : 'staff_contact_book.unread'}
                        />
                      </span>
                    </p>
                    {reply.editable && onEditReply && (
                      <EditReply
                        reply={reply}
                        saving={savingReplyId === reply.id}
                        errorKey={editErrorKey}
                        onEditReply={onEditReply}
                        onStartEdit={onStartEdit}
                      />
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className={BLOCK} aria-labelledby="staff-book-meal">
            <BlockTitle id="staff-book-meal" icon="meal" titleKey="record_page.meal" />
            {mealSlots.map((slot) => (
              <RecordRow
                key={slot}
                labelKey={`record_page.slot.${slot}`}
                record={recordOf('meal', slot)}
              />
            ))}
          </section>

          <section className={BLOCK} aria-labelledby="staff-book-day">
            <BlockTitle id="staff-book-day" icon="mood" titleKey="staff_contact_book.day_title" />
            <RecordRow labelKey="record.item.mood" record={recordOf('mood', 'day')} />
            <RecordRow labelKey="record.item.sleep" record={recordOf('sleep', 'day')} />
          </section>
        </>
      )}
    </section>
  )
}

function BlockTitle({ id, icon, titleKey }: { id: string; icon: IconName; titleKey: string }) {
  return (
    <h2 id={id} className="mt-3 mb-1 text-sm font-bold text-ink-sub">
      <Icon name={icon} className="mr-1.5" />
      <Text k={titleKey} />
    </h2>
  )
}

/** 記録の 1 行：欄の名前・値（大きく）・記録した時刻と人（右に小さく）。まだのときは薄い文字で。 */
function RecordRow({ labelKey, record }: { labelKey: string; record: StaffRecord | null }) {
  return (
    <p className="flex items-baseline gap-3 border-t border-card-line py-3 first-of-type:border-t-0">
      <span className="w-20 shrink-0 text-ink-sub">
        <Text k={labelKey} />
      </span>
      {record ? (
        <>
          <span className="min-w-0 flex-1 text-[17px] font-bold">
            <Text k={`record.value.${record.item}.${record.value}`} />
          </span>
          <span className="shrink-0 text-sm text-ink-sub tabular-nums">
            {timeInJapan(record.recorded_at)}
            <span className="ml-2">{record.recorded_by_name}</span>
          </span>
        </>
      ) : (
        <span className="min-w-0 flex-1 text-ink-sub">
          <Text k="contact_book.not_recorded" />
        </span>
      )}
    </p>
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
        className="mt-1 min-h-11 text-sm font-bold text-primary underline"
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
