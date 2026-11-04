/**
 * 食べた量の絵（お皿の満ち欠け。デザインの決めごと 11.5。#439）。fraction は 0〜1（全部＝1・食べていない＝0）。
 * 飾りなので読み上げない（ボタンの名前は、横の文字）。色は文字と同じ（currentColor）。
 */
export function PlateIcon({ fraction, size = 34 }: { fraction: number; size?: number }) {
  const center = size / 2
  const outer = size / 2 - 3
  const inner = outer - 3
  let fill = null
  if (fraction >= 1) {
    fill = <circle cx={center} cy={center} r={inner} fill="currentColor" />
  } else if (fraction > 0) {
    const angle = 2 * Math.PI * fraction
    const x = center + inner * Math.sin(angle)
    const y = center - inner * Math.cos(angle)
    const large = fraction > 0.5 ? 1 : 0
    fill = (
      <path
        d={`M${center},${center} L${center},${center - inner} A${inner},${inner} 0 ${large} 1 ${x.toFixed(2)},${y.toFixed(2)} Z`}
        fill="currentColor"
      />
    )
  }
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={center} cy={center} r={outer} fill="none" stroke="currentColor" strokeWidth={2} />
      {fill}
    </svg>
  )
}
