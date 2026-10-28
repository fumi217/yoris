import { useEffect, useRef, useState } from 'react'
import { canConfirm } from './confirmTiming'
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
 * 1 回目で、赤い確かめの文と「やめる」に変わる。「やめる」か 2 回目を押すまで、そのまま残す（時間では戻さない。#300）。
 * 1 回目からすぐ（0.5 秒以内）の 2 回目は受け付けない（素早い 2 回のタップで決まらないように）。
 * 確かめの画面（ダイアログ）は出さず、同じ場所で済ませる。
 * ボタンが置き換わってもフォーカスが外れないよう、1 回目のあとは確かめのボタンに、「やめる」のあとは元のボタンに移す
 * （読み上げに確かめの文が伝わる。WCAG 4.1.3・2.4.3。PR #286 みさき）。
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
  const startRef = useRef<HTMLButtonElement>(null)
  const confirmRef = useRef<HTMLButtonElement>(null)
  // 「やめる」で戻ったときだけ、元のボタンにフォーカスを戻す（初めに画面を開いたときは動かさない）
  const stopped = useRef(false)

  useEffect(() => {
    if (firstAt !== null) {
      confirmRef.current?.focus()
    } else if (stopped.current) {
      stopped.current = false
      startRef.current?.focus()
    }
  }, [firstAt])

  const reset = () => setFirstAt(null)
  const stop = () => {
    stopped.current = true
    reset()
  }

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
        ref={startRef}
        type="button"
        disabled={disabled}
        onClick={() => setFirstAt(Date.now())}
        className={`${className} disabled:opacity-60`}
      >
        <Text k={labelKey} />
      </button>
    )
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-3">
      <button
        ref={confirmRef}
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
      <button type="button" onClick={stop} className="text-sm text-sky-700 underline">
        <Text k="layout.confirm_stop" />
      </button>
    </span>
  )
}
