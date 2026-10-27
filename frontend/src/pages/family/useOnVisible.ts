import { useEffect, useRef } from 'react'

/**
 * 要素が画面に出たら、callback を 1 回呼ぶ（callback が null のときは何もしない）。
 * IntersectionObserver が使えない環境では、表示した時点で呼ぶ。
 * 連絡帳の返事のカードと、お問い合わせの職員の返事の発言で使う（返事を見たら既読にする。R-15）。
 */
export function useOnVisible<T extends HTMLElement = HTMLElement>(callback: (() => void) | null) {
  const ref = useRef<T | null>(null)
  const latest = useRef(callback)
  useEffect(() => {
    latest.current = callback
  })
  const enabled = callback !== null
  useEffect(() => {
    const element = ref.current
    if (!enabled || !element) return
    if (typeof IntersectionObserver === 'undefined') {
      latest.current?.()
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          latest.current?.()
          observer.disconnect()
        }
      },
      { threshold: 0.5 },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [enabled])
  return ref
}
