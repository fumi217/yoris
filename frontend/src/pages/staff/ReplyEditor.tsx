import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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
    <form
      className="mt-2 space-y-3 rounded border-2 border-primary p-3"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(selected, note)
      }}
    >
      <p className="text-xs text-gray-600">
        <Text k="staff_contact_book.edit_note" />
      </p>
      <fieldset>
        <legend className="mb-2 text-sm">
          <Text k="reply_page.choose" />
        </legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {reply.template_options.map((template) => {
            const on = selected.includes(template.id)
            return (
              <button
                key={template.id}
                type="button"
                aria-pressed={on}
                onClick={() => setSelected((current) => toggleTemplate(current, template.id))}
                className={`min-h-12 rounded border-2 p-2 text-left ${
                  on ? 'border-primary bg-primary text-white' : 'border-field-line bg-white'
                }`}
              >
                <Text k={template.code} />
              </button>
            )
          })}
        </div>
      </fieldset>
      <label className="block text-sm">
        <Text k="reply_page.note" />
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          aria-invalid={tooLong}
          className="mt-1 block w-full rounded border-2 border-field-line p-2 aria-[invalid=true]:border-red-700"
        />
        <span
          className={`block text-right ${tooLong ? 'font-bold text-red-700' : 'text-gray-600'}`}
        >
          {t('reply_page.note_count', { count: noteLength(note) })}
        </span>
      </label>
      {errorKey && (
        <p role="alert" className="text-sm text-red-700">
          <Text k={errorKey} />
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          disabled={selected.length === 0 || tooLong || saving}
          className="rounded bg-primary px-4 py-2 font-bold text-white disabled:opacity-50"
        >
          <Text k={saving ? 'staff_contact_book.saving_edit' : 'staff_contact_book.save_edit'} />
        </button>
        <button type="button" onClick={onClose} className="text-primary underline">
          <Text k="staff_contact_book.cancel_edit" />
        </button>
      </div>
    </form>
  )
}
