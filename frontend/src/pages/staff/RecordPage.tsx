import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Icon } from '../../components/Icon'
import { useState, type ReactNode } from 'react'
import { type IconName } from '../../components/Icon'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { useMe } from '../../auth/me'
import { ConfirmButton } from '../../components/ConfirmButton'
import { ChangeFlagPanel } from '../../components/change-flags/ChangeFlagPanel'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentName } from '../../components/ResidentName'
import { Ruby } from '../../i18n/Ruby'
import { escapeRubyMarks } from '../../i18n/rubyText'
import { isMemoWriter } from './memoEditorLogic'
import {
  currentRecord,
  DAY_SLOT,
  firstUnrecordedMealSlot,
  VALUES,
  withoutRecord,
  withRecord,
  type Item,
  type StaffContactBook,
  type StaffRecord,
} from './recordValues'
import { PlateIcon } from './PlateIcon'
import { MEAL_SLOTS, monthDay, type MealSlot } from './residentRows'

type Choice = { item: Item; slot: string; value: string }

type SaveResponse = Omit<StaffRecord, 'recorded_by_name'> & { date: string }

const contactBookKey = (residentId: string) => ['staff', 'contact-book', residentId, 'today']

/**
 * 記録の画面（UI-S02。spec 001 の T032）。
 * 押したら、その場で保存する（保存ボタンは置かない）。押し直したら上書きする（US1 の受け入れシナリオ 2・3）。
 * 入居者を選ぶ → 食事の区分 → 値 の 3 タップ以内（FR-006・SC-003）。
 * 食事は、まだ記録していない最初の区分を開いておくので、多くは 2 タップで済む。
 * 今日の記録は、取り消せる（001-T034。誤って別の入居者に記録したとき）。押し間違えないよう、2 回押して取り消す。
 * 見た目（#439。デザインの決めごと 11.5）：上に「今日の記録」の 5 つの札、食べた量にはお皿の絵、機嫌・眠りには顔の絵。
 * 保存・取り消しの知らせは、その欄の見出しの横に出す（画面を遮らない）。
 */
export function RecordPage() {
  const { residentId = '' } = useParams()
  const queryClient = useQueryClient()
  const me = useMe().data
  // 最後にできた操作（保存・取り消し）の知らせと、それがどの欄のことか（その欄の見出しの横に出す。#439）
  const [notice, setNotice] = useState<'saved' | 'cancelled' | null>(null)
  const [noticeAt, setNoticeAt] = useState<Item>('meal')

  const book = useQuery({
    queryKey: contactBookKey(residentId),
    queryFn: () => api.get<StaffContactBook>(`/api/staff/residents/${residentId}/contact-book`),
  })
  const requests = useQuery({
    queryKey: ['staff', 'requests', residentId],
    queryFn: () => api.get<{ requests: unknown[] }>(`/api/staff/residents/${residentId}/requests`),
  })

  const save = useMutation({
    mutationFn: (choice: Choice) =>
      api.put<SaveResponse>(`/api/staff/residents/${residentId}/records`, {
        date: book.data?.date,
        ...choice,
      }),
    onSuccess: (saved, choice) => {
      setNoticeAt(choice.item)
      queryClient.setQueryData<StaffContactBook>(contactBookKey(residentId), (old) =>
        old ? withRecord(old, { ...saved, recorded_by_name: me?.display_name ?? '' }) : old,
      )
      // すぐに押したボタンを光らせたうえで、記録した職員の名前などを読み直す
      // （ログイン中の人がまだ読めていないと、上の名前が空のままになるため。PR #190 の AI チューター）
      void queryClient.invalidateQueries({ queryKey: contactBookKey(residentId) })
      // 入居者一覧の未記録の目印も変わる
      void queryClient.invalidateQueries({ queryKey: ['staff', 'residents'] })
      // 保存で、変化の目印が付く・消えることがある（spec 006 の 006-T008）
      void queryClient.invalidateQueries({
        queryKey: ['staff', 'change-flags', Number(residentId)],
      })
      setNotice('saved')
    },
  })
  const cancel = useMutation({
    mutationFn: (recordId: number) => api.delete(`/api/staff/records/${recordId}`),
    onSuccess: (_, recordId) => {
      queryClient.setQueryData<StaffContactBook>(contactBookKey(residentId), (old) =>
        old ? withoutRecord(old, recordId) : old,
      )
      setNotice('cancelled')
    },
    // 取り消せなかったとき（ほかの職員が先に取り消した 404・日付が変わった 409）も、今の記録を読み直す
    // （欄の表示を実際の状態に合わせる。PR #216 みさき）
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: contactBookKey(residentId) }),
        queryClient.invalidateQueries({ queryKey: ['staff', 'residents'] }),
        queryClient.invalidateQueries({ queryKey: ['staff', 'change-flags', Number(residentId)] }),
      ]),
  })
  const failed = save.isError ? save.error : cancel.isError ? cancel.error : null

  if (book.isPending) return <Message k="layout.loading" />
  if (book.isError) return <Message k={messageKeyOf(book.error)} />
  return (
    <RecordView
      book={book.data}
      waitingRequests={requests.data?.requests.length ?? 0}
      canWriteMemo={isMemoWriter(me?.role)}
      // 入居者が変わったら作り直す（直前の「確かめた」の結果を、別の入居者に引き継がない）
      flagPanel={<ChangeFlagPanel key={book.data.resident.id} residentId={book.data.resident.id} />}
      saving={save.isPending ? save.variables : null}
      cancelling={cancel.isPending}
      notice={notice}
      noticeAt={noticeAt}
      errorKey={failed ? messageKeyOf(failed) : null}
      onChoose={(choice) => {
        cancel.reset()
        setNoticeAt(choice.item)
        save.mutate(choice)
      }}
      onCancel={(recordId) => {
        save.reset()
        const item = book.data.records.find((record) => record.id === recordId)?.item
        if (item) setNoticeAt(item)
        cancel.mutate(recordId)
      }}
    />
  )
}

type ViewProps = {
  book: StaffContactBook
  waitingRequests: number
  // 「様子のメモを書く」を出すか（介護職員・リーダーだけ）
  canWriteMemo: boolean
  // 変化の目印の欄（spec 006 の ChangeFlagPanel。API を読むので、テストでは渡さない）
  flagPanel?: ReactNode
  // 保存中の値（押したボタンだけ「保存中」にし、続けて押せないようにする）
  saving: Choice | null | undefined
  cancelling: boolean
  notice: 'saved' | 'cancelled' | null
  // 知らせ・エラーを出す欄（なければ食事の欄）
  noticeAt?: Item
  errorKey: string | null
  onChoose: (choice: Choice) => void
  onCancel: (recordId: number) => void
}

// 欄の見出しの id（「今日の記録」の札から移る先）
const SECTION_ID: Record<Item, string> = {
  meal: 'record-meal',
  mood: 'record-mood',
  sleep: 'record-sleep',
}
// 食べた量の絵（お皿の満ち欠け）の割合。「食事なし」は絵を付けず、別のボタンにする
const MEAL_FRACTION: Record<string, number> = { '10': 1, '8': 0.8, '5': 0.5, '2': 0.2, '0': 0 }
// 機嫌・眠りの顔の絵（飾り）
const FACE: Record<string, IconName> = {
  smile: 'face-good',
  good: 'face-good',
  normal: 'face-normal',
  low: 'face-low',
  poor: 'face-low',
}
// 選ばれたボタンの右上の ✔（色だけで示さない。1.4.1）
const SELECTED_MARK =
  'absolute top-1.5 right-1.5 flex size-[22px] items-center justify-center rounded-full bg-white text-xs text-primary'

/** 画面の中身（テストではこれを直接出す）。 */
export function RecordView({
  book,
  waitingRequests,
  canWriteMemo,
  flagPanel,
  saving,
  cancelling,
  notice,
  noticeAt = 'meal',
  errorKey,
  onChoose,
  onCancel,
}: ViewProps) {
  const { t } = useTranslation()
  const [mealSlot, setMealSlot] = useState<MealSlot>(() => firstUnrecordedMealSlot(book.records))
  const { resident } = book
  // 「今日の記録」の札から、その欄へ移る（食事の札は、その区分を開く）
  const jump = (item: Item, slot?: MealSlot) => {
    if (slot) setMealSlot(slot)
    document.getElementById(SECTION_ID[item])?.scrollIntoView({ block: 'start' })
  }
  const status = (item: Item) =>
    item === noticeAt ? <SectionStatus notice={notice} errorKey={errorKey} /> : null
  const common = { records: book.records, saving, cancelling, onChoose, onCancel }

  return (
    <section className="space-y-4 p-4">
      <Link
        to="/staff"
        className="-my-2 inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary"
      >
        <Icon name="prev" />
        <Text k="record_page.back" />
      </Link>

      <div className="space-y-4 rounded-2xl border border-card-line bg-card p-4">
        <div className="flex items-center gap-3">
          <span className="flex w-16 shrink-0 flex-col items-center rounded-2xl bg-page py-1.5 leading-tight">
            <span className="text-xs font-bold text-ink-sub">
              <Text k="resident_list.room" />
            </span>
            <span className="text-2xl font-bold">{resident.room}</span>
          </span>
          <div className="min-w-0">
            <h1 className="text-2xl font-bold sm:text-[28px]">
              <ResidentName name={resident.display_name} ruby={resident.display_name_ruby} />
            </h1>
            <p className="text-sm text-ink-sub">
              <Ruby text={t('record_page.date', monthDay(book.date))} />
            </p>
          </div>
        </div>
        <TodayTiles records={book.records} onJump={jump} />
      </div>

      {/* 変化の目印の欄（目印があるときだけ）。記録を付ける前に目に入るよう、記録のボタンより上に置く
          （docs/画面設計.md「5」の 2。spec 006 の 006-T015）。この画面は事務員には開けないので、欄も出ない */}
      {flagPanel}

      {/* 返事待ち・写真・様子のメモの入り口（docs/画面設計.md の「5」の 3・4） */}
      <div className="grid gap-2.5 sm:grid-cols-3">
        {waitingRequests > 0 && (
          // 職員の返事の画面（UI-S03。001-T062）
          <EntryLink
            to={`/staff/residents/${resident.id}/requests`}
            icon="request-waiting"
            urgent
            label={<Ruby text={t('record_page.waiting_requests', { count: waitingRequests })} />}
            sub={<Text k="record_page.waiting_sub" />}
          />
        )}
        {/* 写真を載せる（spec 005 の T015。職員の 4 つの役割すべて。画面はさとこ） */}
        <EntryLink
          to={`/staff/residents/${resident.id}/album`}
          icon="camera"
          label={<Text k="record_page.album" />}
        />
        {canWriteMemo && (
          // 様子のメモを書く（UI-S05。spec 007 の T012。介護職員・リーダーだけ。画面はみさき）
          <EntryLink
            to={`/staff/residents/${resident.id}/memos/new`}
            icon="memo"
            label={<Text k="memo.write" />}
          />
        )}
      </div>

      <RecordCard
        id={SECTION_ID.meal}
        icon="meal"
        title={<Text k="record_page.meal" />}
        status={status('meal')}
      >
        <div role="tablist" className="grid grid-cols-4 gap-1 rounded-2xl bg-page p-1">
          {MEAL_SLOTS.map((slot) => {
            const record = currentRecord(book.records, 'meal', slot)
            const selected = slot === mealSlot
            return (
              <button
                key={slot}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setMealSlot(slot)}
                className={`flex min-h-14 flex-col items-center justify-center gap-0.5 rounded-xl px-1 ${
                  selected
                    ? 'bg-card font-bold text-ink shadow-[0_1px_3px_rgb(15_31_61/0.25)]'
                    : 'text-ink-sub'
                }`}
              >
                {/* 狭い欄では短い名前（朝・昼・夜）にする（4 つが重ならないように）。広い欄は「朝ごはん」 */}
                <span className="text-sm whitespace-nowrap @md:hidden">
                  <Text k={`record.slot.${slot}`} />
                </span>
                <span className="hidden text-base whitespace-nowrap @md:inline">
                  <Text k={`record_page.slot.${slot}`} />
                </span>
                <span
                  className={`flex items-center gap-1 text-xs ${record ? 'font-bold text-green-800' : ''}`}
                >
                  {record ? (
                    <>
                      <Icon name="check" />
                      <Text k={shortValueKey('meal', record.value)} />
                    </>
                  ) : slot === 'snack' ? (
                    '—'
                  ) : (
                    <Text k="record_page.not_recorded" />
                  )}
                </span>
              </button>
            )
          })}
        </div>
        {/* 区分と問いは 1 つの文にする（言語ごとに語順・区切りが違うため。英語で「LunchHow…」とつながらないように） */}
        <p className="font-bold text-ink-sub">
          <Ruby
            text={t('record_page.meal_question', { slot: t(`record_page.slot.${mealSlot}`) })}
          />
        </p>
        <Choices
          // 区分を変えたら、取り消しの「もう一度押す」を戻す
          key={mealSlot}
          item="meal"
          slot={mealSlot}
          {...common}
        />
      </RecordCard>

      <div className="grid gap-4 sm:grid-cols-2">
        <RecordCard
          id={SECTION_ID.mood}
          icon="mood"
          title={<Text k="record_page.mood" />}
          status={status('mood')}
        >
          <Choices item="mood" slot={DAY_SLOT} {...common} />
        </RecordCard>
        <RecordCard
          id={SECTION_ID.sleep}
          icon="sleep"
          title={<Text k="record_page.sleep" />}
          status={status('sleep')}
        >
          <Choices item="sleep" slot={DAY_SLOT} {...common} />
        </RecordCard>
      </div>

      {/* 職員の連絡帳の見返し（UI-S04。001-T033） */}
      <Link
        to={`/staff/residents/${resident.id}/contact-book`}
        className="flex min-h-14 items-center gap-3 rounded-2xl border border-card-line bg-card px-4 py-2.5 font-bold text-primary-dark hover:bg-primary-soft"
      >
        <Icon name="contact-book" className="text-lg" />
        <span className="flex-1">
          <Text k="record_page.to_contact_book" />
          <span className="block text-xs font-semibold text-ink-sub">
            <Text k="record_page.to_contact_book_sub" />
          </span>
        </span>
        <Icon name="next" className="text-ink-sub" />
      </Link>
    </section>
  )
}

/** 値の短い名前の辞書のキー（「今日の記録」の札・区分の切り替えに出す。「食事なし」は短くする）。 */
function shortValueKey(item: Item, value: string): string {
  return item === 'meal' && value === 'none'
    ? 'record_page.meal_none_short'
    : `record.value.${item}.${value}`
}

/** 「今日の記録」の 5 つの札（朝・昼・夜・機嫌・眠り）。押すと、その欄へ移る。 */
function TodayTiles({
  records,
  onJump,
}: {
  records: StaffRecord[]
  onJump: (item: Item, slot?: MealSlot) => void
}) {
  const tiles: { item: Item; slot: string; labelKey: string; mealSlot?: MealSlot }[] = [
    { item: 'meal', slot: 'breakfast', labelKey: 'record.slot.breakfast', mealSlot: 'breakfast' },
    { item: 'meal', slot: 'lunch', labelKey: 'record.slot.lunch', mealSlot: 'lunch' },
    { item: 'meal', slot: 'dinner', labelKey: 'record.slot.dinner', mealSlot: 'dinner' },
    { item: 'mood', slot: DAY_SLOT, labelKey: 'record.item.mood' },
    { item: 'sleep', slot: DAY_SLOT, labelKey: 'record.item.sleep' },
  ]
  return (
    <div className="space-y-1.5">
      <h2 className="text-sm font-bold text-ink-sub">
        <Text k="record_page.today" />
      </h2>
      <ul className="grid grid-cols-5 gap-1.5 sm:gap-2">
        {tiles.map((tile) => {
          const record = currentRecord(records, tile.item, tile.slot)
          return (
            <li key={tile.labelKey} className="min-w-0">
              <button
                type="button"
                onClick={() => onJump(tile.item, tile.mealSlot)}
                className={`flex h-full min-h-16 w-full flex-col items-start gap-1 rounded-xl px-1.5 py-1.5 text-left sm:px-2 ${
                  record
                    ? 'border border-transparent bg-green-100 text-green-800'
                    : 'border border-dashed border-field-line bg-card text-ink-sub'
                }`}
              >
                <span className="flex items-center gap-1 text-xs font-bold whitespace-nowrap sm:text-sm">
                  <Text k={tile.labelKey} />
                  {record && <Icon name="check" className="text-xs" />}
                </span>
                <span
                  className={`text-xs leading-snug [overflow-wrap:anywhere] sm:text-sm ${record ? 'font-bold' : ''}`}
                >
                  <Text
                    k={record ? shortValueKey(tile.item, record.value) : 'record_page.not_recorded'}
                  />
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** 返事待ち・写真・様子のメモの入り口（丸いアイコン・文字・矢印の面）。返事待ちは、目立つ色。 */
function EntryLink({
  to,
  icon,
  label,
  sub,
  urgent = false,
}: {
  to: string
  icon: IconName
  label: ReactNode
  sub?: ReactNode
  urgent?: boolean
}) {
  return (
    <Link
      to={to}
      className={`flex min-h-14 items-center gap-3 rounded-2xl border px-2.5 py-2 ${
        urgent
          ? 'border-red-800 bg-red-100 text-red-800'
          : 'border-card-line bg-card hover:bg-primary-soft'
      }`}
    >
      <span
        aria-hidden="true"
        className={`flex size-10 shrink-0 items-center justify-center rounded-full ${
          urgent ? 'bg-white text-red-800' : 'bg-primary-soft text-primary'
        }`}
      >
        <Icon name={icon} />
      </span>
      <span className="min-w-0 flex-1 text-sm leading-snug font-bold">
        {label}
        {sub && <span className="block text-xs font-semibold">{sub}</span>}
      </span>
      <Icon name="next" className={urgent ? '' : 'text-ink-sub'} />
    </Link>
  )
}

/** 1 つの欄の白い面：丸いアイコン・見出し・知らせ、中身。 */
function RecordCard({
  id,
  icon,
  title,
  status,
  children,
}: {
  id: string
  icon: IconName
  title: ReactNode
  status: ReactNode
  children: ReactNode
}) {
  return (
    <section
      aria-labelledby={id}
      className="@container min-w-0 scroll-mt-4 space-y-3 rounded-2xl border border-card-line bg-card p-4"
    >
      <div className="flex flex-wrap items-center gap-3">
        <span
          aria-hidden="true"
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary"
        >
          <Icon name={icon} className="text-lg" />
        </span>
        <h2 id={id} className="min-w-0 flex-1 text-lg font-bold">
          {title}
        </h2>
        {status}
      </div>
      {children}
    </section>
  )
}

/** 保存した・取り消した・できなかったの知らせ（その欄の見出しの横。画面を遮らない）。 */
function SectionStatus({
  notice,
  errorKey,
}: {
  notice: 'saved' | 'cancelled' | null
  errorKey: string | null
}) {
  return (
    <p role="status" aria-live="polite" className="text-sm">
      {errorKey ? (
        <span className="font-bold text-red-700">
          <Text k={errorKey} />
        </span>
      ) : (
        notice && (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 font-bold text-green-800">
            <Icon name="check" />
            <Text k={`record_page.${notice}`} />
          </span>
        )
      )}
    </p>
  )
}

type ChoicesProps = {
  item: Item
  slot: string
  records: StaffRecord[]
  saving: Choice | null | undefined
  cancelling: boolean
  onChoose: (choice: Choice) => void
  onCancel: (recordId: number) => void
}

/**
 * 値のボタンの並び。今付いている値は、青の塗り・白い文字・右上の ✔ と aria-pressed で示す。
 * 食べた量はお皿の絵つき（「食事なし」は点線の別のボタン）、機嫌・眠りは顔の絵つき。
 * 記録があれば、下に記録した人と時刻、「この記録を取り消す」（ConfirmButton。2 回目で取り消す）。
 */
function Choices({ item, slot, records, saving, cancelling, onChoose, onCancel }: ChoicesProps) {
  const { t } = useTranslation()
  const record = currentRecord(records, item, slot)
  const current = record?.value ?? null
  const busy = Boolean(saving) || cancelling
  const button = (value: string, className: string, body: ReactNode) => {
    const selected = value === current
    return (
      <button
        key={value}
        type="button"
        aria-pressed={selected}
        disabled={busy}
        onClick={() => onChoose({ item, slot, value })}
        className={`relative disabled:opacity-60 ${className} ${
          selected ? 'border-primary bg-primary text-white' : 'border-field-line bg-card text-ink'
        }`}
      >
        {body}
        {selected && (
          <span aria-hidden="true" className={SELECTED_MARK}>
            <Icon name="check" />
          </span>
        )}
      </button>
    )
  }

  return (
    <div className="space-y-3">
      {item === 'meal' ? (
        <>
          <div className="grid grid-cols-2 gap-2 @sm:grid-cols-3 @md:grid-cols-5">
            {VALUES.meal
              .filter((value) => value !== 'none')
              .map((value) =>
                button(
                  value,
                  'flex min-h-24 flex-col items-center justify-center gap-1.5 rounded-2xl border-2 px-1 py-2',
                  <>
                    <span className={value === current ? 'text-white' : 'text-primary'}>
                      <PlateIcon fraction={MEAL_FRACTION[value] ?? 0} />
                    </span>
                    <span className="text-[15px] leading-snug font-bold whitespace-nowrap">
                      <Text k={`record.value.meal.${value}`} />
                    </span>
                  </>,
                ),
              )}
          </div>
          {button(
            'none',
            'min-h-12 w-full rounded-2xl border-2 border-dashed px-3 font-bold',
            <Text k="record.value.meal.none" />,
          )}
        </>
      ) : (
        <div className="grid gap-2">
          {VALUES[item].map((value) =>
            button(
              value,
              'flex min-h-14 items-center gap-3 rounded-2xl border-2 py-2 pr-10 pl-3.5 text-left font-bold',
              <>
                <Icon
                  name={FACE[value] ?? 'face-normal'}
                  className={`text-2xl ${value === current ? '' : 'text-primary'}`}
                />
                <Text k={`record.value.${item}.${value}`} />
              </>,
            ),
          )}
        </div>
      )}
      {record && (
        <div className="flex flex-wrap items-center justify-between gap-x-3 border-t border-card-line pt-1 text-sm text-ink-sub">
          <span>
            {/* 職員の名前は、ふりがなの書き方として解釈しない（記号を全角にして、文字のまま出す） */}
            <Ruby
              text={t('record_page.recorded_by', {
                name: escapeRubyMarks(record.recorded_by_name),
                time: timeOf(record.recorded_at),
              })}
            />
          </span>
          <ConfirmButton
            // 値を押し直したら、確かめの文を元に戻す
            key={`${record.id}-${record.value}`}
            labelKey="record_page.cancel"
            confirmKey="record_page.cancel_confirm"
            disabled={busy}
            onConfirm={() => onCancel(record.id)}
            className="min-h-11 text-sm text-ink-sub underline"
          />
        </div>
      )}
    </div>
  )
}

/** 日本時間の時刻（"08:42"）。 */
function timeOf(iso: string): string {
  return new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(iso))
}
