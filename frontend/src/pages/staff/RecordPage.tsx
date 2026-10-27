import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { api, messageKeyOf } from '../../api/client'
import { useMe } from '../../auth/me'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { Ruby } from '../../i18n/Ruby'
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
 */
export function RecordPage() {
  const { residentId = '' } = useParams()
  const queryClient = useQueryClient()
  const me = useMe().data
  // 最後にできた操作（保存・取り消し）の知らせ
  const [notice, setNotice] = useState<'saved' | 'cancelled' | null>(null)

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
    onSuccess: (saved) => {
      queryClient.setQueryData<StaffContactBook>(contactBookKey(residentId), (old) =>
        old ? withRecord(old, { ...saved, recorded_by_name: me?.display_name ?? '' }) : old,
      )
      // すぐに押したボタンを光らせたうえで、記録した職員の名前などを読み直す
      // （ログイン中の人がまだ読めていないと、上の名前が空のままになるため。PR #190 の AI チューター）
      void queryClient.invalidateQueries({ queryKey: contactBookKey(residentId) })
      // 入居者一覧の未記録の目印も変わる
      void queryClient.invalidateQueries({ queryKey: ['staff', 'residents'] })
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
      ]),
  })
  const failed = save.isError ? save.error : cancel.isError ? cancel.error : null

  if (book.isPending) return <Message k="layout.loading" />
  if (book.isError) return <Message k={messageKeyOf(book.error)} />
  return (
    <RecordView
      book={book.data}
      waitingRequests={requests.data?.requests.length ?? 0}
      saving={save.isPending ? save.variables : null}
      cancelling={cancel.isPending}
      notice={notice}
      errorKey={failed ? messageKeyOf(failed) : null}
      onChoose={(choice) => {
        cancel.reset()
        save.mutate(choice)
      }}
      onCancel={(recordId) => {
        save.reset()
        cancel.mutate(recordId)
      }}
    />
  )
}

type ViewProps = {
  book: StaffContactBook
  waitingRequests: number
  // 保存中の値（押したボタンだけ「保存中」にし、続けて押せないようにする）
  saving: Choice | null | undefined
  cancelling: boolean
  notice: 'saved' | 'cancelled' | null
  errorKey: string | null
  onChoose: (choice: Choice) => void
  onCancel: (recordId: number) => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function RecordView({
  book,
  waitingRequests,
  saving,
  cancelling,
  notice,
  errorKey,
  onChoose,
  onCancel,
}: ViewProps) {
  const { t } = useTranslation()
  const [mealSlot, setMealSlot] = useState<MealSlot>(() => firstUnrecordedMealSlot(book.records))
  const { resident } = book

  return (
    <section className="space-y-6 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-bold">
          <span className="mr-3 text-base font-normal text-gray-600">{resident.room}</span>
          {/* 入居者の呼び名は、辞書を通さずそのまま出す */}
          {resident.display_name}
        </h1>
        <span>
          <Ruby text={t('record_page.date', monthDay(book.date))} />
        </span>
      </div>

      {waitingRequests > 0 && (
        // 職員の返事の画面（UI-S03。001-T062）
        <Link
          to={`/staff/residents/${resident.id}/requests`}
          className="block rounded border border-sky-700 p-3 text-sky-800"
        >
          <Ruby text={t('record_page.waiting_requests', { count: waitingRequests })} />
        </Link>
      )}

      <p role="status" aria-live="polite" className="min-h-6 text-sm">
        {errorKey ? (
          <span className="text-red-700">
            <Text k={errorKey} />
          </span>
        ) : (
          notice && <Text k={`record_page.${notice}`} />
        )}
      </p>

      <fieldset>
        <legend className="mb-2 font-bold">
          <Text k="record_page.meal" />
        </legend>
        <div role="tablist" className="mb-3 flex gap-2">
          {MEAL_SLOTS.map((slot) => (
            <button
              key={slot}
              type="button"
              role="tab"
              aria-selected={slot === mealSlot}
              onClick={() => setMealSlot(slot)}
              className={`rounded-t border-b-4 px-3 py-2 ${
                slot === mealSlot ? 'border-sky-700 font-bold' : 'border-transparent'
              }`}
            >
              <Text k={`record_page.slot.${slot}`} />
              {currentRecord(book.records, 'meal', slot) !== null && (
                <span aria-hidden="true"> ✔</span>
              )}
            </button>
          ))}
        </div>
        <Choices
          // 区分を変えたら、取り消しの「もう一度押す」を戻す
          key={mealSlot}
          item="meal"
          slot={mealSlot}
          records={book.records}
          saving={saving}
          cancelling={cancelling}
          onChoose={onChoose}
          onCancel={onCancel}
        />
      </fieldset>

      <fieldset>
        <legend className="mb-2 font-bold">
          <Text k="record_page.mood" />
        </legend>
        <Choices
          item="mood"
          slot={DAY_SLOT}
          records={book.records}
          saving={saving}
          cancelling={cancelling}
          onChoose={onChoose}
          onCancel={onCancel}
        />
      </fieldset>

      <fieldset>
        <legend className="mb-2 font-bold">
          <Text k="record_page.sleep" />
        </legend>
        <Choices
          item="sleep"
          slot={DAY_SLOT}
          records={book.records}
          saving={saving}
          cancelling={cancelling}
          onChoose={onChoose}
          onCancel={onCancel}
        />
      </fieldset>

      <div className="flex flex-wrap gap-4 border-t pt-4 text-sky-700 underline">
        {/* 職員の連絡帳の見返し（UI-S04。001-T033） */}
        <Link to={`/staff/residents/${resident.id}/contact-book`}>
          <Text k="record_page.to_contact_book" />
        </Link>
        <Link to="/staff">
          <Text k="record_page.back" />
        </Link>
      </div>
    </section>
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
 * 値のボタンの並び。今付いている値は、色を変えて aria-pressed にする。
 * 記録があれば、下に「この記録を取り消す」（1 回目で確かめの文に変わり、2 回目で取り消す）。
 */
function Choices({ item, slot, records, saving, cancelling, onChoose, onCancel }: ChoicesProps) {
  const record = currentRecord(records, item, slot)
  const current = record?.value ?? null
  const [confirming, setConfirming] = useState(false)
  const busy = Boolean(saving) || cancelling

  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {VALUES[item].map((value) => {
          const selected = value === current
          return (
            <button
              key={value}
              type="button"
              aria-pressed={selected}
              disabled={busy}
              onClick={() => {
                setConfirming(false)
                onChoose({ item, slot, value })
              }}
              className={`min-h-14 rounded border-2 px-3 py-2 text-lg disabled:opacity-60 ${
                selected ? 'border-sky-700 bg-sky-700 text-white' : 'border-gray-300 bg-white'
              }`}
            >
              <Text k={`record.value.${item}.${value}`} />
            </button>
          )
        })}
      </div>
      {record && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (!confirming) {
              setConfirming(true)
              return
            }
            setConfirming(false)
            onCancel(record.id)
          }}
          className={`mt-2 text-sm underline disabled:opacity-60 ${
            confirming ? 'font-bold text-red-700' : 'text-gray-600'
          }`}
        >
          <Text k={confirming ? 'record_page.cancel_confirm' : 'record_page.cancel'} />
        </button>
      )}
    </div>
  )
}
