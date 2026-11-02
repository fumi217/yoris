import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Icon, type IconName } from '../../components/Icon'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import mascotFace from '../../assets/brand/mascot-normal.png'
import { Message } from '../../components/Message'
import { OccupationLabel } from '../../components/OccupationLabel'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
import { stripRuby } from '../../i18n/rubyText'
import {
  aiNoticeKey,
  CHOICES,
  guideFor,
  showsCallIfUrgent,
  chronological,
  marksNoticeRead,
  nextBefore,
  PAGE_SIZE,
  sourceParts,
  type Choice,
  type InquiryMessage,
  type InquirySource,
  type SendResult,
} from './inquiryView'
import { markSentOnce } from './contactBookView'
import { sentAtParts } from './requestsView'
import { useOnVisible } from './useOnVisible'

const MESSAGES_KEY = ['family-inquiry-messages'] as const
const NOTIFICATIONS_KEY = ['family', 'notifications'] as const
// 1 回に送れる文字数（FR-001。API も 500 文字を超えると 422）
const BODY_MAX = 500

/**
 * 家族の「お問い合わせ」（AI に質問する）画面（UI-F05。spec 004 の 004-T020・T048）。
 * 画面に戻ったときの読み直し（職員の返事を出すため。research.md R-16）は、
 * TanStack Query の初期設定（refetchOnWindowFocus）で行う。
 * 見た目はデザインの決めごと 13 章（#348）：AI の発言の横にキャラクター、あいさつと用件の選択肢、
 * 「アプリの案内」のカード、丸い送るボタン。
 */
export function Inquiry() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')
  const [errorKey, setErrorKey] = useState<string | null>(null)
  // 押した用件の選択肢（画面の上だけ。会話には保存しない。FR-001a）
  const [choice, setChoice] = useState<Choice | null>(null)

  const messages = useInfiniteQuery({
    queryKey: MESSAGES_KEY,
    queryFn: ({ pageParam }) =>
      api.get<InquiryMessage[]>(
        `/api/family/inquiry/messages?limit=${PAGE_SIZE}${pageParam ? `&before=${pageParam}` : ''}`,
      ),
    initialPageParam: 0,
    getNextPageParam: nextBefore,
  })

  const send = useMutation({
    mutationFn: (body: string) => api.post<SendResult>('/api/family/inquiry/messages', { body }),
    onSuccess: () => {
      setDraft('')
      setErrorKey(null)
    },
    // AI が止まったときなどは、書いた文を消さずに残す（送り直せる。FR-026）
    onError: (error) => setErrorKey(messageKeyOf(error)),
    onSettled: () => queryClient.invalidateQueries({ queryKey: MESSAGES_KEY }),
  })

  // 職員の返事の発言が画面に出たら、その発言のお知らせを読んだことにする（Issue #244。
  // 連絡帳の返事と同じ決まり。発言ごとに 1 回だけ送る）
  const sent = useRef(new Set<number>())
  const { mutate: markRead } = useMutation({
    mutationFn: (messageId: number) => api.post(`/api/family/inquiry/messages/${messageId}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
    // 送れなかった発言は、次に画面に出たときに、また送れるようにする
    onError: (_error, messageId) => {
      sent.current.delete(messageId)
    },
  })
  const onStaffReplySeen = useCallback(
    (messageId: number) => {
      if (markSentOnce(sent.current, messageId)) markRead(messageId)
    },
    [markRead],
  )

  if (messages.isPending) return <Message k="layout.loading" />
  if (messages.isError) return <Message k={messageKeyOf(messages.error)} />

  return (
    <InquiryView
      messages={chronological(messages.data.pages)}
      hasOlder={messages.hasNextPage}
      onLoadOlder={() => messages.fetchNextPage()}
      draft={draft}
      onDraftChange={setDraft}
      sending={send.isPending ? send.variables : null}
      errorKey={errorKey}
      onSend={() => send.mutate(draft.trim())}
      onStaffReplySeen={onStaffReplySeen}
      choice={choice}
      onChoose={setChoice}
    />
  )
}

type ViewProps = {
  messages: InquiryMessage[]
  hasOlder: boolean
  onLoadOlder: () => void
  draft: string
  onDraftChange: (value: string) => void
  // 送っている途中の質問（答えが決まるまで、最後に出しておく）
  sending: string | null
  errorKey: string | null
  onSend: () => void
  // 職員の返事の発言が画面に出たときに呼ばれる（省略できる。テストでは渡さない）
  onStaffReplySeen?: (messageId: number) => void
  // 押した用件の選択肢と、押したときに呼ばれる関数（省略できる。テストでは渡さないこともある）
  choice?: Choice | null
  onChoose?: (choice: Choice) => void
}

/** 画面の見た目（API を呼ばない。テストではこれを描く）。 */
export function InquiryView({
  messages,
  hasOlder,
  onLoadOlder,
  draft,
  onDraftChange,
  sending,
  errorKey,
  onSend,
  onStaffReplySeen,
  choice = null,
  onChoose = () => {},
}: ViewProps) {
  const { t } = useTranslation()
  // 文字の数え方を backend（500 文字まで）とそろえる（絵文字なども 1 文字と数える。PR #213 さとこ）
  const length = Array.from(draft).length
  const tooLong = length > BODY_MAX
  const canSend = sending === null && draft.trim() !== '' && !tooLong
  const guide = choice ? guideFor(choice) : null
  // 発言が増えた・送り始めたときは、いちばん新しい発言と入力欄が見えるところまで送る（PR #213 さとこ）。
  // 選択肢と入力欄は会話の下にあるので、その下まで送る（下に固定したメニューに隠れないよう、scroll-mb で余白をとる）
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, sending])
  // 選択肢を押したら、案内が見えるところまで送る。入力欄へ案内する選択肢は、入力欄に移る
  const guideRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    if (!guide) return
    guideRef.current?.scrollIntoView({ block: 'nearest' })
    if (guide.focusInput) inputRef.current?.focus()
  }, [choice]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    // 会話が短いときも、入力欄が下に寄るよう、ページを画面の高さいっぱいの縦並びにする（上の枠の高さ 3.8rem を引く）。
    // 下の余白（main の pb-20）を打ち消し、代わりに下のメニューの高さ分の余白を取る。入力欄の本来の位置が、メニューの
    // すぐ上になるので、いちばん下までスクロールしても、入力欄が押し上げられて、最後の内容に重なることがない
    // （余白がゼロだと、本来の位置が画面の下端で、メニューが重なって、入力欄が約 53px 上に押し上げられる。PR #410 ようこさん）
    <div className="-mb-20 flex min-h-[calc(100dvh-3.8rem)] flex-col gap-4 p-4 pb-[var(--family-menu-height)]">
      <h1 className="text-2xl font-bold">
        <Text k="inquiry.title" />
      </h1>
      {/* AI がお答えできないときは職員に伝えることを、常に出す（FR-012a）。注意ではなく案内なので、薄い青の帯（13.5） */}
      <p className="flex items-start gap-2 rounded-xl bg-primary-soft p-3 text-sm">
        <Icon name="info" className="mt-0.5 shrink-0 text-primary" />
        <Text k="inquiry.handoff_notice" />
      </p>

      {hasOlder && (
        <button type="button" onClick={onLoadOlder} className="text-sm text-primary underline">
          <Text k="inquiry.load_older" />
        </button>
      )}

      <ol aria-live="polite" className="flex flex-col gap-4">
        {/* あいさつは、会話のいちばん上（最初の発言）に置く。新しい発言は、その下へ続く（PR #349 ようこさん）。
            アプリの決まった文で、AI の吹き出しの形にする（「YORIS の AI アシスタントです」と名乗るため） */}
        <li className="flex items-start gap-2">
          <MascotIcon />
          <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white p-3 shadow-sm">
            <p className="text-xs font-bold text-ink-sub">
              <Text k="inquiry.sender_ai" />
            </p>
            <p>
              <Text k="inquiry.greeting" />
            </p>
          </div>
        </li>
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} onStaffReplySeen={onStaffReplySeen} />
        ))}
        {sending !== null && (
          <>
            <FamilyBubble body={sending} />
            <li className="ml-12 flex items-center gap-2 text-sm text-ink-sub">
              {/* 点が並ぶ印（動かさない）。意味は文字で伝える */}
              <span aria-hidden="true" className="flex gap-1">
                <span className="size-1.5 rounded-full bg-primary/50" />
                <span className="size-1.5 rounded-full bg-primary/75" />
                <span className="size-1.5 rounded-full bg-primary" />
              </span>
              <Text k="inquiry.thinking" />
            </li>
          </>
        )}
      </ol>

      {/* 用件の選択肢（FR-001a）。入力欄のすぐ上に置く。押しても AI を呼ばない。
          縦に並べると高さをとり、最新の答えが押し上げられるので、横に並べて折り返す */}
      <p className="-mb-2 ml-1 text-sm font-bold text-ink-sub">
        <Text k="inquiry.choices_title" />
      </p>
      <div
        role="group"
        aria-label={stripRuby(t('inquiry.choices_label'))}
        className="flex flex-wrap gap-2"
      >
        {CHOICES.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => onChoose(value)}
            className={`flex min-h-11 items-center gap-2 rounded-full border py-1.5 pr-4 pl-2 text-left shadow-sm ${
              choice === value
                ? 'border-primary bg-primary-soft font-bold'
                : 'border-card-line bg-white'
            }`}
          >
            <span
              aria-hidden="true"
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary"
            >
              <Icon name={choice === value ? 'check' : CHOICE_ICON[value]} className="text-sm" />
            </span>
            <span>
              <Text k={`inquiry.choice.${value}`} />
            </span>
          </button>
        ))}
      </div>

      {/* 押した選択肢の「アプリの案内」。AI の答えと見た目を分ける（キャラクターなし・枠のあるカード。13.3） */}
      <div ref={guideRef} role="status">
        {guide && (
          <div className="rounded-lg border-2 border-primary bg-white p-3">
            <p className="text-xs font-bold text-primary">
              <Icon name="info" className="mr-1" />
              <Text k="inquiry.guide_label" />
            </p>
            <p className="mt-1">
              <Text k={guide.textKey} />
            </p>
            {guide.link && (
              <Link
                to={guide.link.to}
                className="mt-2 inline-block font-bold text-primary underline"
              >
                <Text k={guide.link.labelKey} />
                <span aria-hidden="true"> ＞</span>
              </Link>
            )}
          </div>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (canSend) onSend()
        }}
        // 入力欄は、下のメニューのすぐ上に固定する（長い会話でも、すぐ書ける。13.5）
        className="sticky bottom-[var(--family-menu-height)] z-10 -mx-4 mt-auto flex flex-col gap-2 border-t border-card-line bg-card px-4 pt-3 pb-3"
      >
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor="inquiry-body" className="text-sm font-bold">
            <Text k="inquiry.input_label" />
          </label>
          <p
            id="inquiry-count"
            className={`text-sm tabular-nums ${tooLong ? 'font-bold text-red-700' : 'text-ink-sub'}`}
          >
            {t('inquiry.count', { count: length })}
          </p>
        </div>
        {guide?.inputHintKey && (
          <p id="inquiry-hint" className="text-sm">
            <Text k={guide.inputHintKey} />
          </p>
        )}
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            id="inquiry-body"
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            rows={2}
            placeholder={stripRuby(t('inquiry.placeholder'))}
            aria-invalid={tooLong}
            aria-describedby={`inquiry-count${guide?.inputHintKey ? ' inquiry-hint' : ''}`}
            className="min-w-0 flex-1 rounded-2xl border border-field-line bg-white p-3"
          />
          {/* 丸い送るボタン。絵だけにせず、読み上げの名前「送る」を付ける（2.5.3・4.1.2。13.3） */}
          <button
            type="submit"
            disabled={!canSend}
            aria-label={stripRuby(t('inquiry.send'))}
            className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-xl text-white shadow-md disabled:bg-primary-soft disabled:text-ink-sub disabled:shadow-none"
          >
            {/* 紙飛行機は左右が非対称で、真ん中に置くと、目には中央に見えない。1px 左下にずらす（PR #390 ようこさん） */}
            <Icon name="send" className="-translate-x-px translate-y-px" />
          </button>
        </div>
        {tooLong && (
          <p className="text-sm text-red-700">
            <Text k="inquiry.too_long" />
          </p>
        )}
        {errorKey && (
          <p role="alert" className="text-red-700">
            <Text k={errorKey} />
          </p>
        )}
      </form>
      {/* 会話のいちばん下の目印（高さ 0）。縦並びの gap の分（16px）が、入力欄の下に残らないよう、上に詰める */}
      <div ref={endRef} className="-mt-4 scroll-mb-44" />
    </div>
  )
}

// 用件の選択肢ごとのアイコン（13.5）。様子＝連絡帳・面会＝面会予約・その他＝知りたいことと同じ
const CHOICE_ICON: Record<(typeof CHOICES)[number], IconName> = {
  condition: 'contact-book',
  visit: 'visits',
  other: 'requests',
}

/** AI を表すキャラクター（ふつうの顔）。飾りなので読み上げない（alt=""。だれの発言かは「AI」の文字で示す）。 */
function MascotIcon() {
  return (
    <span className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white shadow-sm">
      <img src={mascotFace} alt="" width={308} height={263} className="h-auto w-9" />
    </span>
  )
}

function MessageItem({
  message,
  onStaffReplySeen,
}: {
  message: InquiryMessage
  onStaffReplySeen?: (messageId: number) => void
}) {
  if (message.sender === 'family')
    return <FamilyBubble body={message.body} createdAt={message.created_at} />
  if (message.sender === 'staff') return <StaffBubble message={message} onSeen={onStaffReplySeen} />
  return <AiBubble message={message} />
}

function FamilyBubble({ body, createdAt }: { body: string; createdAt?: string }) {
  return (
    <li className="ml-auto max-w-[85%]">
      {/* 自分の発言は、白い吹き出し（右寄せ・薄い枠）。青の塗りは、押せるボタンに見えるので使わない（13.5）。
          AI は、キャラクターと「YORIS（AI）」の文字と影で見分ける */}
      <div className="rounded-2xl rounded-tr-sm border border-card-line bg-white p-3">
        <p className="text-xs font-bold text-ink-sub">
          <Text k="inquiry.sender_family" />
        </p>
        {/* 家族が書いた文は、辞書を通さず文字としてだけ出す（FR-028） */}
        <p className="whitespace-pre-wrap">{body}</p>
      </div>
      {createdAt && (
        <p className="mt-0.5 text-right text-xs text-ink-sub tabular-nums">
          {sentAtParts(createdAt).time}
        </p>
      )}
    </li>
  )
}

function AiBubble({ message }: { message: InquiryMessage }) {
  const noticeKey = aiNoticeKey(message)
  return (
    // AI の発言は、キャラクターと「AI」の文字と吹き出し（13.3）
    <li className="flex items-start gap-2">
      <MascotIcon />
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white p-3 shadow-sm">
        <p className="text-xs font-bold text-ink-sub">
          <Text k="inquiry.sender_ai" />
        </p>
        {noticeKey ? (
          <p>
            <Text k={noticeKey} />
          </p>
        ) : (
          // AI の答えは、辞書を通さず文字としてだけ出す（タグは実行されない。FR-028）
          <p className="whitespace-pre-wrap">{message.body}</p>
        )}
        {showsCallIfUrgent(message) && (
          <p className="mt-1 text-sm">
            <Text k="inquiry.call_if_urgent" />
          </p>
        )}
        {message.sources.length > 0 && (
          <div className="mt-2 rounded-xl bg-page p-2 text-sm">
            <p className="flex items-center gap-1.5 text-xs font-bold text-ink-sub">
              <Icon name="empty-record" />
              <Text k="inquiry.source_records" />
            </p>
            <ul>
              {message.sources.map((source, index) => (
                <SourceItem key={index} source={source} />
              ))}
            </ul>
          </div>
        )}
        {/* AI の答えであることを、答えのそばに常に出す（FR-005） */}
        <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-sub">
          <Icon name="info" className="shrink-0" />
          <Text k="inquiry.ai_notice" />
        </p>
      </div>
    </li>
  )
}

function SourceItem({ source }: { source: InquirySource }) {
  const { t } = useTranslation()
  const { month, day, labelKeys } = sourceParts(source)
  return (
    <li>
      <Ruby text={t('inquiry.source_date', { month, day })} />
      {labelKeys.map((key) => (
        <span key={key}>
          ・<Text k={key} />
        </span>
      ))}
    </li>
  )
}

// 辞書の「{{name}}からの返事」を、名前の前と後ろに分けるための目印（名前には入らない文字）
const NAME_SLOT = '\u0000'

function StaffBubble({
  message,
  onSeen,
}: {
  message: InquiryMessage
  onSeen?: (messageId: number) => void
}) {
  const { t } = useTranslation()
  // 画面に出たら、その発言のお知らせを読んだことにする（電話で対応した発言は送らない）
  const ref = useOnVisible<HTMLLIElement>(
    onSeen && marksNoticeRead(message) ? () => onSeen(message.id) : null,
  )
  // 名前は辞書の文に差し込まず、文字のまま出す（名前の { | } を、ふりがなの書き方と取り違えないため。
  // 語順は辞書の文のまま使えるので、インドネシア語・英語でも同じ形で出せる。PR #213 さとこ）
  const [before, after = ''] = t('inquiry.reply_from', { name: NAME_SLOT }).split(NAME_SLOT)
  return (
    // 職員の返事には、キャラクターを付けない（人の返事。13.2）
    <li ref={ref} className="ml-12 rounded-2xl border border-[#86d3a0] bg-[#dcfce7] p-3 text-ink">
      {/* 職員の返事は「◯◯からの返事」と、AI の答えと区別して出す（FR-005） */}
      <p className="flex flex-wrap items-center gap-x-1 text-xs font-bold text-[#166534]">
        <Icon name="family-message" className="mr-1 shrink-0" />
        <Ruby text={before} />
        {message.staff_name}
        {/* 職種は辞書で引く（「山本（生活相談員）からの返事」。空なら名前だけ。#263） */}
        <OccupationLabel code={message.staff_occupation} />
        <Ruby text={after} />
      </p>
      {message.response_type === 'phone' ? (
        <p>
          <Text k="inquiry.staff_phone_response" />
        </p>
      ) : (
        <>
          {(message.template_codes ?? []).map((code) => (
            <p key={code}>
              <Text k={code} />
            </p>
          ))}
          {/* 職員が書き足した文は、辞書を通さず文字としてだけ出す（FR-028） */}
          {message.note && <p className="whitespace-pre-wrap">{message.note}</p>}
        </>
      )}
    </li>
  )
}
