import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Message } from '../../components/Message'
import { OccupationLabel } from '../../components/OccupationLabel'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import {
  itemKey,
  markSentOnce,
  monthDayOf,
  pickDate,
  shiftDate,
  slotLabelKey,
  timeInJapan,
  todayInJapan,
  valueKey,
  type ContactBookData,
  type ContactReply,
  type ContactSection,
} from './contactBookView'
import { useOnVisible } from './useOnVisible'

const CONTACT_BOOK_KEY = ['family', 'contact-book'] as const
const NOTIFICATIONS_KEY = ['family', 'notifications'] as const

/**
 * 家族の連絡帳（ホーム。UI-F02。spec 001 の T059・docs/画面設計.md「7」）。`/family`
 * 上から、未読の返事のカード（日付に関わらず一番上。カードが画面に出たら自動で既読にする）、
 * その日の読んだ返事、食事 → 機嫌・様子 → 眠り（まだ記録がない欄は「まだ記録されていません」）、
 * 画面の下に「緊急のときは、施設から電話します」。
 * 見る日は URL の `?date=` で決める（なければ今日。日数の制限はない。T094・FR-019）。
 */
export function ContactBook() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const today = todayInJapan()
  const date = pickDate(searchParams.get('date'), today)
  // 今日のときは日付を付けない（API の「今日」と同じ日になる）
  const move = (next: string) => setSearchParams(next === today ? {} : { date: next })
  // 画面を開いたとき・戻ったときに読み直す（リアルタイムの配信は使わない。R-15）
  const book = useQuery({
    queryKey: [...CONTACT_BOOK_KEY, date],
    queryFn: () =>
      api.get<ContactBookData>(
        date === today ? '/api/family/contact-book' : `/api/family/contact-book?date=${date}`,
      ),
  })
  const sent = useRef(new Set<number>())
  const { mutate: markRead } = useMutation({
    mutationFn: (replyId: number) => api.post(`/api/family/replies/${replyId}/read`),
    // 連絡帳は、すぐには読み直さない（読んでいる途中でカードが消えないように。次に開いたとき外れる）
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
    // 送れなかった返事は、次に画面に出たときに、また送れるようにする
    onError: (_error, replyId) => {
      sent.current.delete(replyId)
    },
  })
  const onRead = useCallback(
    (replyId: number) => {
      if (markSentOnce(sent.current, replyId)) markRead(replyId)
    },
    [markRead],
  )

  if (book.isPending) return <Message k="layout.loading" />
  if (book.isError) return <Message k={messageKeyOf(book.error)} />
  return <ContactBookView book={book.data} onRead={onRead} today={today} onMove={move} />
}

type ViewProps = {
  book: ContactBookData
  // 未読の返事のカードが画面に出たときに呼ばれる
  onRead: (replyId: number) => void
  // 日付の切り替えを出すときだけ渡す（今日の日付と、見る日を変える関数）
  today?: string
  onMove?: (date: string) => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function ContactBookView({ book, onRead, today, onMove }: ViewProps) {
  const { t } = useTranslation()
  return (
    <section className="space-y-6 p-4">
      <h1 className="text-xl font-bold">
        <Ruby text={t('contact_book.title', monthDayOf(book.date))} />
      </h1>

      {today !== undefined && onMove && <DayNav date={book.date} today={today} onMove={onMove} />}

      {(book.unread_replies.length > 0 || book.day_replies.length > 0) && (
        <div className="space-y-3">
          {book.unread_replies.map((reply) => (
            <ReplyCard key={reply.id} reply={reply} today={book.date} unread onRead={onRead} />
          ))}
          {book.day_replies.map((reply) => (
            <ReplyCard key={reply.id} reply={reply} today={book.date} unread={false} />
          ))}
        </div>
      )}

      {book.sections.map((section) => (
        <RecordSection key={section.item} section={section} />
      ))}

      <p className="text-sm text-gray-600">
        <Text k="contact_book.emergency" />
      </p>
    </section>
  )
}

/** 見る日の切り替え。今日より先は選べない（記録がないため）。 */
function DayNav({
  date,
  today,
  onMove,
}: {
  date: string
  today: string
  onMove: (date: string) => void
}) {
  const isToday = date === today
  const button = 'min-h-12 rounded border-2 border-gray-300 px-3 disabled:opacity-40'
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <button type="button" className={button} onClick={() => onMove(shiftDate(date, -1))}>
          <span aria-hidden="true">◀ </span>
          <Text k="contact_book.prev_day" />
        </button>
        <button
          type="button"
          className={button}
          disabled={isToday}
          onClick={() => onMove(shiftDate(date, 1))}
        >
          <Text k="contact_book.next_day" />
          <span aria-hidden="true"> ▶</span>
        </button>
        {!isToday && (
          <button type="button" className={button} onClick={() => onMove(today)}>
            <Text k="contact_book.go_today" />
          </button>
        )}
      </div>
      <label className="block text-sm">
        <Text k="contact_book.pick_date" />
        <input
          type="date"
          value={date}
          max={today}
          onChange={(event) => {
            const picked = pickDate(event.target.value, today)
            if (picked !== date) onMove(picked)
          }}
          className="ml-2 min-h-10 rounded border-2 border-gray-300 px-2"
        />
      </label>
    </div>
  )
}

/** 返事のカード。未読のものは、画面に出たら onRead を 1 回呼ぶ。 */
function ReplyCard({
  reply,
  today,
  unread,
  onRead,
}: {
  reply: ContactReply
  today: string
  unread: boolean
  onRead?: (replyId: number) => void
}) {
  const { t } = useTranslation()
  const ref = useOnVisible(unread && onRead ? () => onRead(reply.id) : null)
  return (
    <article
      ref={ref}
      className={`space-y-2 rounded border-2 p-4 ${
        unread ? 'border-sky-700 bg-sky-50' : 'border-gray-300'
      }`}
    >
      <p className="text-lg font-bold">
        <span aria-hidden="true">{reply.theme_emoji} </span>
        <Text k={reply.theme_code} />
      </p>
      <p className="text-sm">
        {/* 職員の名前は、辞書を通さず、そのまま出す。職種は辞書で引く（「シティ（介護職員）からの返事」。#263） */}
        <span className="font-bold">
          {reply.replied_by_name}
          <OccupationLabel code={reply.replied_by_occupation} />
        </span>
        <Text k="contact_book.reply_from" />
        <span className="ml-2 text-gray-600">{timeInJapan(reply.replied_at)}</span>
        {unread && (
          <span className="ml-2 rounded bg-sky-700 px-2 py-0.5 text-xs text-white">
            <Text k="contact_book.unread_reply" />
          </span>
        )}
      </p>
      {reply.contact_book_date !== today && (
        <p className="text-sm text-gray-600">
          <Ruby text={t('contact_book.reply_date', monthDayOf(reply.contact_book_date))} />
        </p>
      )}
      <ul className="list-inside list-disc">
        {reply.template_codes.map((code) => (
          <li key={code}>
            <Text k={code} />
          </li>
        ))}
      </ul>
      {/* 職員が書き足した文は、辞書を通さず、文字としてだけ出す */}
      {reply.note && <p className="whitespace-pre-wrap">{reply.note}</p>}
      {reply.edited && (
        <p className="text-xs text-gray-600">
          <Text k="contact_book.edited" />
        </p>
      )}
    </article>
  )
}

function RecordSection({ section }: { section: ContactSection }) {
  return (
    <div>
      <h2 className="mb-1 font-bold">
        <Text k={itemKey(section.item)} />
      </h2>
      <ul className="divide-y border-y">
        {section.slots.map((slot) => {
          const label = slotLabelKey(section.item, slot.slot)
          return (
            <li key={slot.slot} className="flex flex-wrap justify-between gap-2 py-2">
              <span>
                {label && (
                  <span className="mr-2 font-bold">
                    <Text k={label} />
                  </span>
                )}
                {slot.record ? (
                  <Text k={valueKey(section.item, slot.record.value)} />
                ) : (
                  <span className="text-gray-500">
                    <Text k={slot.message_key ?? 'contact_book.not_recorded'} />
                  </span>
                )}
              </span>
              {slot.record && (
                <span className="text-sm text-gray-600">
                  {slot.record.recorded_by_name} {timeInJapan(slot.record.recorded_at)}
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
