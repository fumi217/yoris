import { useEffect, useRef, useState } from 'react'
import { canConfirm, CONFIRM_RESET_MS } from './confirmTiming'
import { Text } from './Text'

type Props = {
  // 初めのボタンの文言（例：「この記録を取り消す」）
  labelKey: string
  // 1 回目に押したあとの文言（例：「もう一度押すと取り消します」）
  confirmKey: string
  // 決めている途中の文言（例：「取り消しています」）。なければ labelKey のまま
  busyKey?: string
  busy?: boolean
  disabled?: boolean
  onConfirm: () => void
  className?: string
}

/**
 * 2 回押して決めるボタン（記録の取り消し・面会の予約の取り消しなど、押し間違えると困る操作）。
 * 1 回目で、赤い確かめの文と「やめる」に変わる。5 秒たつと元に戻る。
 * 1 回目からすぐ（0.5 秒以内）の 2 回目は受け付けない（素早い 2 回のタップで決まらないように）。
 * 確かめの画面（ダイアログ）は出さず、同じ場所で済ませる。
 */
export function ConfirmButton({
  labelKey,
  confirmKey,
  busyKey,
  busy = false,
  disabled = false,
  onConfirm,
  className = '',
}: Props) {
  const [firstAt, setFirstAt] = useState<number | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const reset = () => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
    setFirstAt(null)
  }
  // 画面を離れたら、待っている時計を止める
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
    },
    [],
  )

  if (busy && busyKey) {
    return (
      <button type="button" disabled className={`${className} opacity-60`}>
        <Text k={busyKey} />
      </button>
    )
  }
  if (firstAt === null) {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          setFirstAt(Date.now())
          timer.current = setTimeout(reset, CONFIRM_RESET_MS)
        }}
        className={`${className} disabled:opacity-60`}
      >
        <Text k={labelKey} />
      </button>
    )
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-3">
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (!canConfirm(firstAt, Date.now())) return
          reset()
          onConfirm()
        }}
        className={`${className} font-bold text-red-700 disabled:opacity-60`}
      >
        <Text k={confirmKey} />
      </button>
      <button type="button" onClick={reset} className="text-sm text-sky-700 underline">
        <Text k="layout.confirm_stop" />
      </button>
    </span>
  )
}
