import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '../../components/Icon'
import { Text } from '../../components/Text'
import type { StaffReply } from './recordValues'
import { MAX_NOTE_LENGTH, noteLength, toggleTemplate } from './replyForm'

type Props = {
  reply: StaffReply
  saving: boolean
  errorKey: string | null
  onSave: (templateIds: number[], note: string) => void
  onClose: () => void
}

/**
 * 返事をした当日だけ、返事を直す欄（spec 001 の T063・FR-030）。連絡帳の見返しの返事の下に出す。
 * 選んでいた定型文と書き足しから始め、定型文は 1 つ以上・書き足しは 100 文字まで（返事の画面と同じ決まり）。
 * 直しても、家族にもう一度お知らせはしない（返事の取り消しはしない）。
 */
export function ReplyEditor({ reply, saving, errorKey, onSave, onClose }: Props) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<number[]>(reply.template_ids)
  const [note, setNote] = useState(reply.note ?? '')
  const tooLong = noteLength(note) > MAX_NOTE_LENGTH

  return (
    // 枠で囲まず、薄い背景の面にする（カードの中にカードを重ねない）。中身は返事の画面と同じ形（#459）
    <form
      className="mt-3 space-y-4 rounded-xl bg-page px-4 pt-3 pb-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(selected, note)
      }}
    >
      <p className="text-sm text-ink-sub">
        <Icon name="info" className="mr-1.5" />
        <Text k="staff_contact_book.edit_note" />
      </p>
      <fieldset>
        <legend className="mb-1.5 text-sm font-bold text-ink-sub">
          <Text k="reply_page.choose" />
        </legend>
        <ul className="border-t border-card-line">
          {reply.template_options.map((template) => {
            const on = selected.includes(template.id)
            return (
              <li key={template.id} className="border-b border-card-line">
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => setSelected((current) => toggleTemplate(current, template.id))}
                  className={`flex min-h-13 w-full items-center gap-3.5 py-2 text-left leading-normal ${
                    on ? 'font-bold text-primary-dark' : ''
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`flex size-6 shrink-0 items-center justify-center rounded-full text-xs ${
                      on ? 'bg-primary text-white' : 'ring-2 ring-[#b7c0cd] ring-inset'
                    }`}
                  >
                    {on && <Icon name="check" />}
                  </span>
                  <span>
                    <Text k={template.code} />
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </fieldset>
      <label className="block text-sm font-bold text-ink-sub">
        <Text k="reply_page.note" />
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          aria-invalid={tooLong}
          className="mt-1.5 block w-full rounded-xl border border-field-line bg-card p-3 text-base font-normal text-ink aria-[invalid=true]:border-2 aria-[invalid=true]:border-red-700"
        />
        <span
          className={`mt-1 block text-right font-normal ${tooLong ? 'font-bold text-red-700' : 'text-ink-sub'}`}
        >
          {t('reply_page.note_count', { count: noteLength(note) })}
        </span>
      </label>
      {errorKey && (
        <p role="alert" className="text-sm font-bold text-red-700">
          <Text k={errorKey} />
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          type="submit"
          disabled={selected.length === 0 || tooLong || saving}
          className="min-h-12 rounded-[14px] bg-primary px-6 font-bold text-white disabled:opacity-50"
        >
          <Text k={saving ? 'staff_contact_book.saving_edit' : 'staff_contact_book.save_edit'} />
        </button>
        <button
          type="button"
          onClick={onClose}
          className="min-h-11 font-bold text-primary underline"
        >
          <Text k="staff_contact_book.cancel_edit" />
        </button>
      </div>
    </form>
  )
}
