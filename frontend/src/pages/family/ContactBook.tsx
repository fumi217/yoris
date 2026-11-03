import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { themeIconName } from '../../components/themeIcon'
import { useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { Icon, type IconName } from '../../components/Icon'
import { Message } from '../../components/Message'
import { OccupationLabel } from '../../components/OccupationLabel'
import { SectionHeader } from '../../components/SectionHeader'
import { StatusBadge } from '../../components/StatusBadge'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { DateNavigator } from './DateNavigator'
import {
  itemKey,
  markSentOnce,
  monthDayOf,
  pickDate,
  sectionStatus,
  slotLabelKey,
  timeInJapan,
  todayInJapan,
  valueKey,
  weekdayOf,
  type ContactBookData,
  type ContactMemo,
  type ContactReply,
  type ContactSection,
  type ContactSlot,
} from './contactBookView'
import { Mascot } from './Mascot'
import { useOnVisible } from './useOnVisible'

const CONTACT_BOOK_KEY = ['family', 'contact-book'] as const
const NOTIFICATIONS_KEY = ['family', 'notifications'] as const

/**
 * 家族の連絡帳（ホーム。UI-F02。spec 001 の T059・docs/画面設計.md「7」）。`/family`
 * 上から、未読の返事のカード（日付に関わらず一番上。カードが画面に出たら自動で既読にする）、
 * その日の読んだ返事、食事 → 機嫌・様子 → 眠り（まだ記録がない欄は「まだ記録されていません」）、
 * 画面の下に「緊急のときは、施設からお電話します」（FR-028）。
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

  return (
    <>
      {book.isPending ? (
        <Message k="layout.loading" />
      ) : book.isError ? (
        <Message k={messageKeyOf(book.error)} />
      ) : (
        // 右下に固定したキャラクターの分、下をあける（幅 320px 以下では、キャラクターは末尾に置く）
        <div className="pb-[4.5rem] [@media(max-width:320px)]:pb-0 [@media(max-height:400px)]:pb-0">
          <ContactBookView book={book.data} onRead={onRead} today={today} onMove={move} />
        </div>
      )}
      <Mascot />
    </>
  )
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
  const { t, i18n } = useTranslation()
  const isToday = today === undefined || book.date === today
  return (
    <section className="space-y-6 p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold">
            <Ruby
              text={t('contact_book.title', {
                ...monthDayOf(book.date),
                weekday: weekdayOf(book.date, i18n.language),
              })}
            />
          </h1>
          <p className="text-ink-sub">
            <Text k={isToday ? 'contact_book.subtitle_today' : 'contact_book.subtitle_other'} />
          </p>
        </div>
        {/* 1 週間のまとめの入口（FR-036）。右に置き、狭い幅では見出しの下に、幅いっぱいで出す */}
        <Link
          to="/family/weekly"
          className="flex min-h-12 w-full items-center gap-3 rounded-xl bg-primary-soft py-1.5 pl-2 pr-4 font-bold text-primary-dark shadow-md hover:bg-primary hover:text-white hover:shadow-lg active:shadow-sm sm:w-auto"
        >
          <span
            aria-hidden="true"
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white text-primary"
          >
            <Icon name="weekly" />
          </span>
          <span className="flex-1">
            <Text k="contact_book.weekly_summary" />
          </span>
          <Icon name="next" />
        </Link>
      </div>

      {today !== undefined && onMove && (
        <DateNavigator date={book.date} today={today} onMove={onMove} />
      )}

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

      {/* 食事・機嫌・眠りを、1 枚の大きなカードに。中は、薄い線で分ける（カードの中にカードを重ねない） */}
      <Card>
        <div className="divide-y divide-card-line">
          {book.sections.map((section) => (
            <RecordSection key={section.item} section={section} />
          ))}
        </div>
      </Card>

      {/* 様子のメモ（spec 007 の FR-012）：承認されたものだけ。AI で整えた日本語であることを、控えめに添える */}
      {book.memos.length > 0 && <MemoSection memos={book.memos} />}

      {/* 緊急の案内（FR-028）。警告の赤・オレンジにはせず、淡い青の案内の帯にする */}
      <p className="flex items-center gap-3 rounded-xl bg-primary-soft p-4 text-sm font-bold">
        <Icon name="phone" className="text-lg text-primary" />
        <Text k="contact_book.emergency" />
      </p>
    </section>
  )
}

/** 様子のメモ：1 枚の白い面に、書いた時刻の順で並べる。職員の名前・時刻は、各メモの下。 */
function MemoSection({ memos }: { memos: ContactMemo[] }) {
  return (
    <Card>
      <div className="space-y-4">
        <SectionHeader
          icon="memo"
          title={<Text k="contact_book.memos_title" />}
          description={<Text k="contact_book.memos_description" />}
        />
        <ul className="divide-y divide-card-line">
          {memos.map((memo) => (
            <li key={memo.id} className="space-y-1 py-3 first:pt-0 last:pb-0">
              {/* 整えた日本語は、辞書を通さず、文字としてだけ出す */}
              <p className="whitespace-pre-wrap text-lg break-words">{memo.text}</p>
              <p className="text-xs text-ink-sub">
                <span className="font-bold">
                  {memo.author_name}
                  <OccupationLabel code={memo.author_occupation} />
                </span>
                <span className="ml-2">{timeInJapan(memo.written_at)}</span>
              </p>
            </li>
          ))}
        </ul>
        <p className="flex items-center gap-1.5 text-sm text-ink-sub">
          <Icon name="info" className="shrink-0" />
          <Text k="contact_book.memos_ai_note" />
        </p>
      </div>
    </Card>
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
      className={`space-y-1 border-l-4 py-2 pl-4 pr-3 ${
        unread ? 'border-primary bg-unread' : 'border-card-line'
      }`}
    >
      {/* テーマは、小さなラベルに。主役は、職員が書いた文（note）。テンプレートの文は、補足にする */}
      <p className="flex flex-wrap items-center gap-x-2 text-sm text-ink-sub">
        <span>
          <Icon name={themeIconName(reply.theme_code)} className="mr-1 text-primary" />
          <Text k={reply.theme_code} />
        </span>
        {unread && (
          <span className="rounded bg-primary px-2 py-0.5 text-xs text-white">
            <Text k="contact_book.unread_reply" />
          </span>
        )}
      </p>
      {/* 職員の書いた文は、辞書を通さず、文字としてだけ出す */}
      {reply.note && <p className="whitespace-pre-wrap text-lg">{reply.note}</p>}
      <ul className={`list-inside list-disc ${reply.note ? 'text-sm text-ink-sub' : 'text-base'}`}>
        {reply.template_codes.map((code) => (
          <li key={code}>
            <Text k={code} />
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink-sub">
        {/* 職員の名前は、辞書を通さず、そのまま出す。職種は辞書で引く（「シティ（介護職員）からの返事」。#263） */}
        <span className="font-bold">
          {reply.replied_by_name}
          <OccupationLabel code={reply.replied_by_occupation} />
        </span>
        <Text k="contact_book.reply_from" />
        <span className="ml-2">{timeInJapan(reply.replied_at)}</span>
        {reply.contact_book_date !== today && (
          <span className="ml-2">
            <Ruby text={t('contact_book.reply_date', monthDayOf(reply.contact_book_date))} />
          </span>
        )}
        {reply.edited && (
          <span className="ml-2">
            <Text k="contact_book.edited" />
          </span>
        )}
      </p>
    </article>
  )
}

// 食事・機嫌・眠りの、見出しのアイコンと、説明の辞書のキー
const SECTION_ICON: Record<string, IconName> = { meal: 'meal', mood: 'mood', sleep: 'sleep' }
// 食事の区分ごとの小さなアイコン（色は控えめ）
const SLOT_ICON: Record<string, IconName> = {
  breakfast: 'breakfast',
  lunch: 'lunch',
  dinner: 'dinner',
  snack: 'snack',
}

const STATUS_TONE = { recorded: 'success', partial: 'neutral', unrecorded: 'neutral' } as const

function RecordSection({ section }: { section: ContactSection }) {
  const status = sectionStatus(section)
  return (
    <div className="space-y-4 py-5 first:pt-0 last:pb-0">
      <SectionHeader
        icon={SECTION_ICON[section.item] ?? 'meal'}
        title={<Text k={itemKey(section.item)} />}
        description={<Text k={`contact_book.section.${section.item}`} />}
        aside={
          <StatusBadge tone={STATUS_TONE[status]}>
            <Text k={`contact_book.status.${status}`} />
          </StatusBadge>
        }
      />
      {section.item === 'meal' ? (
        <MealSlots section={section} />
      ) : (
        section.slots.map((slot) => <DaySlot key={slot.slot} section={section} slot={slot} />)
      )}
    </div>
  )
}

/**
 * 食事：朝・昼・夜（記録があるときはおやつも）。広い幅は横に 3 列、狭い幅（sm より小さい）は 1 列にして、
 * 「アイコンと区分／値と記録した人・時刻」を 1 行で見せる（おやつも同じ列に並ぶ。単語の途中で折り返さない）。
 */
function MealSlots({ section }: { section: ContactSection }) {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {section.slots.map((slot) => {
        const label = slotLabelKey(section.item, slot.slot)
        return (
          <li
            key={slot.slot}
            className="flex min-w-0 items-start gap-3 rounded-xl bg-page p-3 break-keep sm:block sm:space-y-1 sm:break-normal"
          >
            <p className="flex w-20 shrink-0 items-center gap-2 text-sm font-bold sm:w-auto">
              {SLOT_ICON[slot.slot] && (
                <Icon name={SLOT_ICON[slot.slot]} className="text-ink-sub" />
              )}
              {label && <Text k={label} />}
            </p>
            {/* 区分の幅をそろえ、値は左揃えにして、1 列のときも位置がそろうようにする */}
            <div className="min-w-0 flex-1 space-y-0.5 text-left sm:space-y-1">
              {slot.record ? (
                <>
                  <p>
                    <Text k={valueKey(section.item, slot.record.value)} />
                  </p>
                  <p className="text-xs text-ink-sub">
                    {slot.record.recorded_by_name} {timeInJapan(slot.record.recorded_at)}
                  </p>
                </>
              ) : (
                <p className="text-sm text-ink-sub">
                  <Text k={slot.message_key ?? 'contact_book.not_recorded'} />
                </p>
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/** 機嫌・眠り（1 日 1 つ）。記録がないときは、中央にやわらかい案内を出す。 */
function DaySlot({ section, slot }: { section: ContactSection; slot: ContactSlot }) {
  if (!slot.record) {
    return (
      <EmptyState
        icon="empty-record"
        title={<Text k={slot.message_key ?? 'contact_book.not_recorded'} />}
        description={<Text k="contact_book.wait_for_record" />}
      />
    )
  }
  return (
    <div className="space-y-1 rounded-xl bg-page p-4">
      <p className="font-bold">
        <Text k={valueKey(section.item, slot.record.value)} />
      </p>
      <p className="text-xs text-ink-sub">
        {slot.record.recorded_by_name} {timeInJapan(slot.record.recorded_at)}
      </p>
    </div>
  )
}
