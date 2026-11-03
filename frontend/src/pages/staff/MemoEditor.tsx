import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Icon } from '../../components/Icon'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { api } from '../../api/client'
import { useMe } from '../../auth/me'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { ResidentName } from '../../components/ResidentName'
import { stripRuby } from '../../i18n/rubyText'
import {
  canConfirm,
  canWithdraw,
  canWriteMemo,
  errorKeyFor,
  initialLang,
  isEditable,
  isStateChanged,
  langKey,
  needsBackTranslation,
  originalChanged,
  originalLength,
  originalProblem,
  rewrittenChanged,
  rewrittenProblem,
  SOURCE_LANGS,
  statusKey,
  textLength,
  warningKeys,
  type Memo,
  type SourceLang,
} from './memoEditorLogic'
import type { StaffContactBook } from './recordValues'

type Resident = StaffContactBook['resident']

/** 画面で押せる操作（押している最中の表示と、失敗の文言を、1 つにまとめるため）。 */
export type MemoAction = 'submit' | 'save' | 'back_translate' | 'confirm' | 'withdraw'

// 一覧に並べる自分のメモの数（新しい順）
const MINE_LIMIT = 10

/** 「確かめました」の上に出す案内の辞書のキー。日本語の職員には、訳し戻しの話をしない（FR-007）。 */
function confirmKey(confirmable: boolean, backTranslated: boolean): string {
  const base = confirmable ? 'memo.confirm_hint' : 'memo.confirm_blocked'
  return backTranslated ? base : `${base}_ja`
}

/**
 * 様子のメモを書く画面（UI-S05。spec 007 の T011・T019）。`/staff/residents/:residentId/memos/new`
 *
 * 原文の言語を選んで母国語で書き（500 文字まで）、「日本語にする」を押すと、AI が、書いた内容を
 * 足さず減らさずに、やさしい日本語に整え、職員の言語に訳し戻す。原文・整えた日本語・訳し戻しを並べて出す。
 * - 下書きを先に保存してから AI を呼ぶ（API を 2 つに分けてある）ので、AI が止まっても、
 *   書いた原文は消えない（FR-020・R-09）。止まったときは、同じボタンで、もう一度整えられる
 * - 下書き・戻されたメモは、原文も整えた日本語も直せる（FR-008）。整えた日本語を直したら、訳し戻して
 *   から「確かめました」を押す（古い訳し戻しを見て確かめないため）
 * - 「確かめました」で承認待ちになる（FR-009）。承認待ち・下書き・戻されたメモは取り下げられる（FR-010）。
 *   戻されたときは、理由を出す（FR-013）
 * - 画面の下に、この入居者について書いた自分のメモの一覧を置き、あとから開いて直せる
 * - 画面の上に、いつも「急変・事故は、すぐに電話で連絡してください」（FR-016）
 * - 家族に出すのは、承認されたものだけ（FR-012）
 */
export function MemoEditor() {
  const { residentId = '' } = useParams()
  const me = useMe().data
  const queryClient = useQueryClient()
  const [lang, setLang] = useState<SourceLang | null>(null)
  const [text, setText] = useState('')
  // 開いているメモ（最初に「日本語にする」を押したときに作る下書き、または一覧から開いたもの）
  const [memo, setMemo] = useState<Memo | null>(null)
  // 開いているメモの原文・整えた日本語を直している途中の文
  const [editedOriginal, setEditedOriginal] = useState('')
  const [editedRewritten, setEditedRewritten] = useState('')

  // 入居者の呼び名・居室（記録の画面で読んだものがあれば、それを使う）
  const book = useQuery({
    queryKey: ['staff', 'contact-book', residentId, 'today'],
    queryFn: () => api.get<StaffContactBook>(`/api/staff/residents/${residentId}/contact-book`),
  })
  // この入居者について、自分が書いたメモ（新しい順）
  const mine = useQuery({
    queryKey: ['staff', 'memos', residentId],
    queryFn: () => api.get<Memo[]>(`/api/staff/memos?resident_id=${residentId}`),
    // 書けない役割は 403 になる（画面は「書けません」の案内で止まる）ので、読みに行かない
    enabled: canWriteMemo(me?.role),
  })

  /** 開いているメモを、サーバーの最新に入れ替える（直している途中の文も、そろえる）。 */
  const show = (next: Memo) => {
    setMemo(next)
    setEditedOriginal(next.original_text)
    setEditedRewritten(next.rewritten_text ?? '')
  }

  const act = useMutation({
    mutationFn: async (action: MemoAction): Promise<Memo> => {
      if (action === 'submit') {
        let current = memo
        if (current === null) {
          // 先に下書き（原文）を保存する。これが済めば、AI が止まっても原文は残る
          current = await api.post<Memo>(`/api/staff/residents/${residentId}/memos`, {
            original_text: text.trim(),
            source_lang: lang ?? initialLang(me?.language),
          })
          show(current)
        } else if (originalChanged(current, editedOriginal)) {
          // 原文を直したときは、直した原文を保存してから、整え直す（整えた日本語は消える）
          current = await api.patch<Memo>(`/api/staff/memos/${current.id}`, {
            original_text: editedOriginal.trim(),
          })
          show(current)
        }
        return api.post<Memo>(`/api/staff/memos/${current.id}/rewrite`)
      }
      if (memo === null) throw new Error('memo is not open')
      if (action === 'save') {
        // 整えた日本語を直した。保存して、日本語以外の職員は、直した文を訳し戻す
        const saved = await api.patch<Memo>(`/api/staff/memos/${memo.id}`, {
          rewritten_text: editedRewritten.trim(),
        })
        show(saved)
        if (!needsBackTranslation(me?.language)) return saved
        return api.post<Memo>(`/api/staff/memos/${memo.id}/rewrite`, { back_translate_only: true })
      }
      if (action === 'back_translate') {
        // 保存した整えた日本語はそのままで、訳し戻しだけをやり直す。訳し戻しだけが失敗したあと
        // （保存は済んでいる）、直した日本語を消さずに、やり直せるようにする
        return api.post<Memo>(`/api/staff/memos/${memo.id}/rewrite`, { back_translate_only: true })
      }
      return api.post<Memo>(`/api/staff/memos/${memo.id}/${action}`)
    },
    onSuccess: (saved) => {
      show(saved)
      void queryClient.invalidateQueries({ queryKey: ['staff', 'memos'] })
    },
    onError: async (error) => {
      // 別の画面で状態が変わっていた（409）：最新を読み直して、開いているメモを入れ替える。
      // 古い状態のまま、押せないボタンを見せ続けない。読み直せなくても、案内は出る
      if (!isStateChanged(error) || memo === null) return
      try {
        show(await api.get<Memo>(`/api/staff/memos/${memo.id}`))
      } catch {
        // 案内（「いまの状態では、この操作はできません」）は、errorKeyFor で出る
      }
      void queryClient.invalidateQueries({ queryKey: ['staff', 'memos'] })
    },
  })

  // 一覧から開く・新しく書く。直している途中の文と、前の失敗の表示は、持ち越さない
  const open = (next: Memo) => {
    act.reset()
    show(next)
    setLang(next.source_lang)
  }
  const startNew = () => {
    act.reset()
    setMemo(null)
    setText('')
    setEditedOriginal('')
    setEditedRewritten('')
    setLang(null)
  }

  // 介護職員・リーダー以外は、書く前に案内する（書いて押してから 403 になる手間を、むだにしない。
  // 守りは API の 403。PR #249 ゆう）。入居者の呼び名を読むなどの hooks は、上で呼んでおく
  if (!canWriteMemo(me?.role)) return <Message k="memo.not_allowed" />

  return (
    <MemoEditorView
      residentId={residentId}
      resident={book.data?.resident ?? null}
      lang={lang ?? initialLang(me?.language)}
      onLang={setLang}
      text={text}
      onText={setText}
      memo={memo}
      pending={act.isPending}
      errorKey={act.isError ? errorKeyFor(act.error) : null}
      onSubmit={() => act.mutate('submit')}
      staffLanguage={me?.language}
      editedOriginal={editedOriginal}
      onEditedOriginal={setEditedOriginal}
      editedRewritten={editedRewritten}
      onEditedRewritten={setEditedRewritten}
      action={act.isPending ? act.variables : null}
      onSave={() => act.mutate('save')}
      onBackTranslate={() => act.mutate('back_translate')}
      onConfirm={() => act.mutate('confirm')}
      onWithdraw={() => act.mutate('withdraw')}
      mine={mine.data?.slice(0, MINE_LIMIT)}
      onOpen={open}
      onNew={startNew}
    />
  )
}

type ViewProps = {
  residentId: string
  resident: Resident | null
  lang: SourceLang
  onLang: (lang: SourceLang) => void
  // まだ保存していない、新しく書く原文
  text: string
  onText: (text: string) => void
  // 開いているメモ。まだ保存していなければ null
  memo: Memo | null
  // 何かの操作を押している最中
  pending: boolean
  errorKey: string | null
  onSubmit: () => void
  // ここから、直す・確かめる・取り下げる・一覧（007-T019）。
  // 職員の表示言語（日本語なら訳し戻さない。FR-007）
  staffLanguage?: string
  // 開いているメモを直している途中の文。省くと、保存した文を出す
  editedOriginal?: string
  onEditedOriginal?: (text: string) => void
  editedRewritten?: string
  onEditedRewritten?: (text: string) => void
  // 押している最中の操作（その操作のボタンだけ、文言を変える）
  action?: MemoAction | null
  onSave?: () => void
  // 訳し戻しだけをやり直す（保存した整えた日本語はそのまま）
  onBackTranslate?: () => void
  onConfirm?: () => void
  onWithdraw?: () => void
  // この入居者について、自分が書いたメモ
  mine?: Memo[]
  onOpen?: (memo: Memo) => void
  onNew?: () => void
}

/** 画面の中身（テストではこれを直接出す）。 */
export function MemoEditorView({
  residentId,
  resident,
  lang,
  onLang,
  text,
  onText,
  memo,
  pending,
  errorKey,
  onSubmit,
  staffLanguage,
  editedOriginal,
  onEditedOriginal,
  editedRewritten,
  onEditedRewritten,
  action = null,
  onSave,
  onBackTranslate,
  onConfirm,
  onWithdraw,
  mine = [],
  onOpen,
  onNew,
}: ViewProps) {
  const { t } = useTranslation()
  // 直せるのは、書く前・下書き・戻されたとき。承認待ち・承認済み・取り下げたメモは、読むだけ
  const readOnlyMemo = memo !== null && !isEditable(memo.status) ? memo : null
  const editable = readOnlyMemo === null
  // 原文を直している途中の文（書く前は、新しく書く原文）
  const original = memo !== null ? (editedOriginal ?? memo.original_text) : text
  const rewrittenValue = editedRewritten ?? memo?.rewritten_text ?? ''
  const problem = originalProblem(original)
  const rewritten = memo?.rewritten_text ?? null
  const rewrittenIssue = rewrittenProblem(rewrittenValue)
  // 原文が日本語のときは、ボタンの名前が「整える」（FR-003）
  const isJapanese = (memo ? memo.source_lang : lang) === 'ja'
  const rewrittenEdited = memo !== null && rewrittenChanged(memo, rewrittenValue)
  const warnings = memo ? warningKeys(memo.warnings) : []
  const confirmable =
    memo !== null && canConfirm(memo, staffLanguage, { original, rewritten: rewrittenValue })

  return (
    <section className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        <Text k="memo.write" />
        {resident && (
          <span className="ml-3 text-base font-normal">
            <span className="mr-2 text-gray-600">{resident.room}</span>
            <ResidentName name={resident.display_name} ruby={resident.display_name_ruby} />
          </span>
        )}
      </h1>

      {/* 急変・事故は、このメモでは伝えられない。いつも出す（FR-016） */}
      <p role="note" className="rounded border border-red-700 bg-red-50 p-3 font-bold text-red-800">
        <Icon name="urgent-call" className="mr-2" />
        <Text k="memo.call_if_urgent" />
      </p>

      {memo && <StatusBox memo={memo} />}

      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (editable && problem === null && !pending) onSubmit()
        }}
      >
        <label className="block text-sm">
          <Text k="memo.language" />
          <select
            value={lang}
            disabled={memo !== null}
            onChange={(event) => onLang(event.target.value as SourceLang)}
            className="mt-1 block w-full rounded border-2 border-field-line p-2"
          >
            {SOURCE_LANGS.map((code) => (
              <option key={code} value={code}>
                {stripRuby(t(langKey(code)))}
              </option>
            ))}
          </select>
        </label>

        {readOnlyMemo ? (
          // 承認待ち・承認済み・取り下げたメモの原文。直せない。文字としてだけ出す（FR-017）
          <div className="space-y-1">
            <p className="text-sm font-bold">
              <Text k="memo.original" />
            </p>
            <p
              lang={readOnlyMemo.source_lang}
              className="whitespace-pre-wrap rounded-lg border border-card-line bg-card p-3"
            >
              {readOnlyMemo.original_text}
            </p>
          </div>
        ) : (
          <label className="block text-sm">
            <Text k={memo ? 'memo.edit_original' : 'memo.input_label'} />
            {memo && !originalChanged(memo, original) && (
              <span className="ml-3 text-xs text-gray-600">
                <Text k="memo.original_saved" />
              </span>
            )}
            <textarea
              value={original}
              lang={memo ? memo.source_lang : lang}
              onChange={(event) => (memo ? onEditedOriginal : onText)?.(event.target.value)}
              rows={5}
              aria-invalid={problem === 'too_long'}
              className="mt-1 block w-full rounded border-2 border-field-line p-2 aria-[invalid=true]:border-red-700"
            />
            <span
              className={`block text-right ${
                problem === 'too_long' ? 'font-bold text-red-700' : 'text-gray-600'
              }`}
            >
              {t('memo.counter', { count: originalLength(original) })}
            </span>
          </label>
        )}

        {problem === 'too_long' && editable && (
          <p role="alert" className="text-red-700">
            <Text k="memo.too_long" />
          </p>
        )}

        {editable && (
          <button
            type="submit"
            disabled={problem !== null || pending}
            className="w-full rounded bg-primary p-3 text-lg font-bold text-white disabled:opacity-50"
          >
            {pending && (action === null || action === 'submit') ? (
              <Text k={isJapanese ? 'memo.polishing' : 'memo.thinking'} />
            ) : errorKey && !rewritten ? (
              <Text k="memo.retry" />
            ) : rewritten ? (
              <Text k={isJapanese ? 'memo.polish_redo' : 'memo.redo'} />
            ) : (
              <Text k={isJapanese ? 'memo.polish' : 'memo.to_japanese'} />
            )}
          </button>
        )}

        {errorKey && (
          // AI が止まったときも、原文は消えない（上に出ている）。時間をおいて、もう一度押せる
          <p role="alert" className="rounded border border-red-700 p-3 text-red-700">
            <Text k={errorKey} />
          </p>
        )}
      </form>

      {rewritten !== null && memo && (
        <section aria-label={stripRuby(t('memo.rewritten'))} className="space-y-2">
          <p className="text-sm font-bold">
            <Text k="memo.rewritten" />
          </p>
          {editable ? (
            <div className="space-y-2">
              <textarea
                value={rewrittenValue}
                lang="ja"
                onChange={(event) => onEditedRewritten?.(event.target.value)}
                rows={5}
                aria-label={stripRuby(t('memo.edit_rewritten'))}
                aria-invalid={rewrittenIssue === 'too_long'}
                className="block w-full rounded border-2 border-primary p-3 aria-[invalid=true]:border-red-700"
              />
              <span
                className={`block text-right ${
                  rewrittenIssue === null ? 'text-gray-600' : 'font-bold text-red-700'
                }`}
              >
                {t('memo.rewritten_counter', { count: textLength(rewrittenValue) })}
              </span>
              {rewrittenIssue !== null && (
                <p role="alert" className="text-red-700">
                  <Icon name="warning" className="mr-1" />
                  <Text
                    k={
                      rewrittenIssue === 'empty'
                        ? 'memo.rewritten_empty'
                        : 'memo.rewritten_too_long'
                    }
                  />
                </p>
              )}
              {rewrittenEdited && (
                <button
                  type="button"
                  disabled={rewrittenIssue !== null || pending}
                  onClick={onSave}
                  className="min-h-11 rounded border-2 border-primary px-4 py-2 font-bold text-primary disabled:opacity-50"
                >
                  {pending && action === 'save' ? (
                    <Text k="memo.back_translating" />
                  ) : (
                    <Text
                      k={needsBackTranslation(staffLanguage) ? 'memo.save_back' : 'memo.save_edit'}
                    />
                  )}
                </button>
              )}
            </div>
          ) : (
            // 整えた日本語は、辞書を通さず、文字としてだけ出す（FR-017）
            <p className="whitespace-pre-wrap rounded border-2 border-primary p-3">{rewritten}</p>
          )}
          <p className="text-xs text-gray-600">
            <Text k="memo.ai_notice" />
          </p>
        </section>
      )}

      {rewritten !== null && needsBackTranslation(staffLanguage) && memo && (
        <section aria-label={stripRuby(t('memo.back_translation'))} className="space-y-1">
          <p className="text-sm font-bold">
            <Text k="memo.back_translation" />
          </p>
          {memo.back_translation !== null && !rewrittenEdited ? (
            // 訳し戻しも、文字としてだけ出す（FR-017）。原文と同じ意味か、本人が確かめる（FR-007）
            <p
              lang={staffLanguage}
              className="whitespace-pre-wrap rounded-lg border border-card-line bg-card p-3"
            >
              {memo.back_translation}
            </p>
          ) : (
            editable && (
              <p className="text-sm text-gray-700">
                <Text k="memo.no_back_translation" />
              </p>
            )
          )}
          {/* 直した日本語は保存できたのに、訳し戻しだけが失敗したとき（サーバーは、直すと訳し戻しを空にする）。
              「確かめました」が押せず、「もう一度日本語にする」では直した文が消えてしまうので、
              訳し戻しだけをやり直すボタンを出す（直しの途中のときは、上の「直した文を訳し戻す」を使う） */}
          {editable && memo.back_translation === null && !rewrittenEdited && onBackTranslate && (
            <button
              type="button"
              disabled={pending}
              onClick={onBackTranslate}
              className="min-h-11 rounded border-2 border-primary px-4 py-2 font-bold text-primary disabled:opacity-50"
            >
              {pending && action === 'back_translate' ? (
                <Text k="memo.back_translating" />
              ) : (
                <Text k="memo.save_back" />
              )}
            </button>
          )}
        </section>
      )}

      {warnings.length > 0 && (
        <div role="note" className="rounded border-2 border-amber-700 bg-amber-50 p-3">
          <p className="font-bold">
            <Icon name="warning" className="mr-1" />
            <Text k="memo.warnings_title" />
          </p>
          <ul className="list-disc pl-5 text-sm">
            {warnings.map((key) => (
              <li key={key}>
                <Text k={key} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {memo && isEditable(memo.status) && rewritten !== null && (
        <div className="space-y-2">
          <ul className="list-disc pl-5 text-sm">
            <li>
              <Text k="memo.check_other_names" />
            </li>
            <li>
              <Text k="memo.check_medical" />
            </li>
          </ul>
          <p className="text-sm text-gray-700">
            <Text k={confirmKey(confirmable, needsBackTranslation(staffLanguage))} />
          </p>
          <button
            type="button"
            disabled={!confirmable || pending}
            onClick={onConfirm}
            className="w-full rounded bg-primary p-3 text-lg font-bold text-white disabled:opacity-50"
          >
            <Text k={pending && action === 'confirm' ? 'memo.confirming' : 'memo.confirm'} />
          </button>
        </div>
      )}

      {memo && canWithdraw(memo.status) && (
        <button
          type="button"
          disabled={pending}
          onClick={onWithdraw}
          className="min-h-11 rounded border-2 border-ink-sub bg-white px-4 py-2 disabled:opacity-50"
        >
          <Text k={pending && action === 'withdraw' ? 'memo.withdrawing' : 'memo.withdraw'} />
        </button>
      )}

      <MineList memos={mine} openId={memo?.id ?? null} onOpen={onOpen} onNew={onNew} />

      <Link to={`/staff/residents/${residentId}`} className="inline-block text-primary underline">
        <Text k="memo.back_to_record" />
      </Link>
    </section>
  )
}

/** 開いているメモの状態。戻されたときは、理由を目立たせる（FR-013）。 */
function StatusBox({ memo }: { memo: Memo }) {
  return (
    <div className="space-y-1">
      <p className="font-bold">
        <Text k="memo.status_label" />：<Text k={statusKey(memo.status)} />
      </p>
      {memo.status === 'draft' && memo.rewritten_text !== null && (
        <p className="text-sm">
          <Text k="memo.draft_saved" />
        </p>
      )}
      {memo.status === 'pending' && (
        <p className="text-sm">
          <Text k="memo.pending_note" />
        </p>
      )}
      {memo.status === 'approved' && (
        <p className="text-sm">
          <Text k="memo.approved_note" />
        </p>
      )}
      {memo.status === 'returned' && memo.return_reason && (
        <div role="note" className="rounded border-2 border-amber-700 bg-amber-50 p-3">
          <p className="font-bold">
            <Text k="memo.return_reason_title" />
          </p>
          {/* 戻した人が書いた理由は、辞書を通さず、文字としてだけ出す（FR-017） */}
          <p className="whitespace-pre-wrap">{memo.return_reason}</p>
        </div>
      )}
    </div>
  )
}

/** この入居者について、自分が書いたメモ。押すと、同じ画面で開いて直せる。 */
function MineList({
  memos,
  openId,
  onOpen,
  onNew,
}: {
  memos: Memo[]
  openId: number | null
  onOpen?: (memo: Memo) => void
  onNew?: () => void
}) {
  return (
    <section aria-labelledby="memo-mine" className="space-y-2">
      <h2 id="memo-mine" className="font-bold">
        <Text k="memo.mine_title" />
      </h2>
      {memos.length === 0 ? (
        <p className="text-sm text-gray-700">
          <Text k="memo.mine_empty" />
        </p>
      ) : (
        <ul className="divide-y rounded border">
          {memos.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
              <div className="min-w-0 space-y-1">
                <p className="text-sm">
                  <span className="mr-2 font-bold">
                    <Text k={statusKey(item.status)} />
                  </span>
                  {item.memo_date}
                </p>
                {/* 原文は、辞書を通さず、文字としてだけ出す（FR-017） */}
                <p lang={item.source_lang} className="truncate text-sm text-gray-700">
                  {item.original_text}
                </p>
              </div>
              <button
                type="button"
                disabled={item.id === openId}
                aria-pressed={item.id === openId}
                onClick={() => onOpen?.(item)}
                className="min-h-11 rounded border-2 border-ink-sub bg-white px-4 py-2 disabled:opacity-50"
              >
                <Text k="memo.open" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {openId !== null && (
        <button type="button" onClick={onNew} className="min-h-11 text-primary underline">
          <Text k="memo.new_memo" />
        </button>
      )}
    </section>
  )
}
