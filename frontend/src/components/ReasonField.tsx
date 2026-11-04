import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Ruby } from '../i18n/Ruby'
import { stripRuby } from '../i18n/rubyText'
import { Text } from './Text'

type Props = {
  value: string
  onChange: (value: string) => void
  // 長すぎる（赤く示し、案内を出す）
  tooLong: boolean
  // 2 回押して決めるボタンが確かめの状態のあいだと、送っているあいだは直せない（#317）。
  // 確かめた内容と送る内容がずれないように、直したいときは「やめる」で戻す
  locked: boolean
}

/**
 * 取り消し・休みの「理由」の入力欄（面会の予約の取り消しと、予約の入った日を休みにするときに使う。必須・200 文字まで）。
 *
 * `locked` のあいだは `readOnly`（灰色）にする。`disabled` にしないのは、キーボードで行けて、
 * 読み上げで内容が読めるようにするため（WCAG 1.3.1・4.1.2）。案内の文は、状態が変わったら読み上げに伝える。
 * 入力した理由は職員が自由に書いた文なので、辞書は通さない。
 */
export function ReasonField({ value, onChange, tooLong, locked }: Props) {
  const guideId = useId()
  const { t } = useTranslation()
  // 案内の文に出す「やめる」は、言語ごとのボタンの文字をそのまま入れる（英語では「Cancel」。
  // 文に「Cancel」と固定で書くと、「予約を取り消す」のボタンと取り違えるため）
  const guide = locked
    ? t('visit_settings.reason_locked', { stop: stripRuby(t('layout.confirm_stop')) })
    : t('visit_settings.reason_hint')

  return (
    <>
      <label className="block text-sm">
        <Text k="visit_settings.reason" />
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          readOnly={locked}
          rows={2}
          aria-invalid={tooLong}
          aria-describedby={guideId}
          className="bg-card mt-1 block w-full rounded border-2 border-ink-sub p-2 read-only:bg-gray-100 read-only:text-gray-700 aria-[invalid=true]:border-red-700"
        />
      </label>
      <p id={guideId} aria-live="polite" className="text-sm text-gray-700">
        <Ruby text={guide} />
      </p>
      {tooLong && (
        <p className="text-red-700">
          <Text k="visit_settings.reason_too_long" />
        </p>
      )}
    </>
  )
}
