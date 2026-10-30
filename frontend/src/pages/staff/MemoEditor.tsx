import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { api } from '../../api/client'
import { useMe } from '../../auth/me'
import { Message } from '../../components/Message'
import { Text } from '../../components/Text'
import { stripRuby } from '../../i18n/rubyText'
import {
  canWriteMemo,
  errorKeyFor,
  initialLang,
  langKey,
  originalLength,
  originalProblem,
  SOURCE_LANGS,
  type Memo,
  type SourceLang,
} from './memoEditorLogic'
import type { StaffContactBook } from './recordValues'

type Resident = StaffContactBook['resident']

/**
 * 様子のメモを書く画面（UI-S05。spec 007 の T011）。`/staff/residents/:residentId/memos/new`
 *
 * 原文の言語を選んで母国語で書き（500 文字まで）、「日本語にする」を押すと、AI が、書いた内容を
 * 足さず減らさずに、やさしい日本語に整える。原文と整えた日本語を並べて出す。
 * - 下書きを先に保存してから AI を呼ぶ（API を 2 つに分けてある）ので、AI が止まっても、
 *   書いた原文は消えない（FR-020・R-09）。保存したあとの原文は、読み取り専用にする
 *   （原文を直す API は作り込み）。止まったときは、同じボタンで、もう一度整えられる
 * - 画面の上に、いつも「急変・事故は、すぐに電話で連絡してください」（FR-016）
 * - 家族に出すのは、確かめて・承認されたものだけ（作り込み）。今は下書きとして保存するだけ
 */
export function MemoEditor() {
  const { residentId = '' } = useParams()
  const me = useMe().data
  const queryClient = useQueryClient()
  const [lang, setLang] = useState<SourceLang | null>(null)
  const [text, setText] = useState('')
  // 保存した下書き（最初に「日本語にする」を押したときに作る）
  const [memo, setMemo] = useState<Memo | null>(null)

  // 入居者の呼び名・居室（記録の画面で読んだものがあれば、それを使う）
  const book = useQuery({
    queryKey: ['staff', 'contact-book', residentId, 'today'],
    queryFn: () => api.get<StaffContactBook>(`/api/staff/residents/${residentId}/contact-book`),
  })

  const submit = useMutation({
    mutationFn: async () => {
      let id = memo?.id
      if (id === undefined) {
        // 先に下書き（原文）を保存する。これが済めば、AI が止まっても原文は残る
        const created = await api.post<Memo>(`/api/staff/residents/${residentId}/memos`, {
          original_text: text.trim(),
          source_lang: lang ?? initialLang(me?.language),
        })
        setMemo(created)
        id = created.id
      }
      return api.post<Memo>(`/api/staff/memos/${id}/rewrite`)
    },
    onSuccess: (rewritten) => {
      setMemo(rewritten)
      void queryClient.invalidateQueries({ queryKey: ['staff', 'memos'] })
    },
  })

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
      pending={submit.isPending}
      errorKey={submit.isError ? errorKeyFor(submit.error) : null}
      onSubmit={() => submit.mutate()}
    />
  )
}

type ViewProps = {
  residentId: string
  resident: Resident | null
  lang: SourceLang
  onLang: (lang: SourceLang) => void
  text: string
  onText: (text: string) => void
  // 保存した下書き。まだ保存していなければ null
  memo: Memo | null
  pending: boolean
  errorKey: string | null
  onSubmit: () => void
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
}: ViewProps) {
  const { t } = useTranslation()
  const problem = originalProblem(text)
  // 保存したあとは、原文を直せない（直す API は作り込み）ので、読み取り専用にする
  const saved = memo !== null
  const rewritten = memo?.rewritten_text ?? null

  return (
    <section className="space-y-4 p-4">
      <h1 className="text-xl font-bold">
        <Text k="memo.write" />
        {resident && (
          <span className="ml-3 text-base font-normal">
            <span className="mr-2 text-gray-600">{resident.room}</span>
            {/* 入居者の呼び名は、辞書を通さずそのまま出す */}
            {resident.display_name}
          </span>
        )}
      </h1>

      {/* 急変・事故は、このメモでは伝えられない。いつも出す（FR-016） */}
      <p role="note" className="rounded border border-red-700 bg-red-50 p-3 font-bold text-red-800">
        🚨 <Text k="memo.call_if_urgent" />
      </p>

      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (problem === null && !pending) onSubmit()
        }}
      >
        <label className="block text-sm">
          <Text k="memo.language" />
          <select
            value={lang}
            disabled={saved}
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

        {saved ? (
          // 保存した原文。直せない（読み取り専用）。文字としてだけ出す（FR-017）
          <div className="space-y-1">
            <p className="text-sm font-bold">
              <Text k="memo.original" />
              <span className="ml-3 text-xs font-normal text-gray-600">
                <Text k="memo.original_saved" />
              </span>
            </p>
            <p
              lang={memo.source_lang}
              className="whitespace-pre-wrap rounded-lg border border-card-line bg-card p-3"
            >
              {memo.original_text}
            </p>
          </div>
        ) : (
          <label className="block text-sm">
            <Text k="memo.input_label" />
            <textarea
              value={text}
              lang={lang}
              onChange={(event) => onText(event.target.value)}
              rows={5}
              aria-invalid={problem === 'too_long'}
              className="mt-1 block w-full rounded border-2 border-field-line p-2 aria-[invalid=true]:border-red-700"
            />
            <span
              className={`block text-right ${
                problem === 'too_long' ? 'font-bold text-red-700' : 'text-gray-600'
              }`}
            >
              {t('memo.counter', { count: originalLength(text) })}
            </span>
          </label>
        )}

        {problem === 'too_long' && (
          <p role="alert" className="text-red-700">
            <Text k="memo.too_long" />
          </p>
        )}

        <button
          type="submit"
          disabled={(!saved && problem !== null) || pending}
          className="w-full rounded bg-primary p-3 text-lg font-bold text-white disabled:opacity-50"
        >
          {pending ? (
            <Text k="memo.thinking" />
          ) : errorKey ? (
            <Text k="memo.retry" />
          ) : rewritten ? (
            <Text k="memo.redo" />
          ) : (
            <Text k="memo.to_japanese" />
          )}
        </button>

        {errorKey && (
          // AI が止まったときも、原文は消えない（上に出ている）。時間をおいて、もう一度押せる
          <p role="alert" className="rounded border border-red-700 p-3 text-red-700">
            <Text k={errorKey} />
          </p>
        )}
      </form>

      {rewritten !== null && (
        <section aria-label={stripRuby(t('memo.rewritten'))} className="space-y-2">
          <p className="text-sm font-bold">
            <Text k="memo.rewritten" />
          </p>
          {/* 整えた日本語は、辞書を通さず、文字としてだけ出す（FR-017） */}
          <p className="whitespace-pre-wrap rounded border-2 border-primary p-3">{rewritten}</p>
          <p className="text-xs text-gray-600">
            <Text k="memo.ai_notice" />
          </p>
          <p className="text-sm">
            <Text k="memo.draft_saved" />
          </p>
        </section>
      )}

      <Link to={`/staff/residents/${residentId}`} className="inline-block text-primary underline">
        <Text k="memo.back_to_record" />
      </Link>
    </section>
  )
}
