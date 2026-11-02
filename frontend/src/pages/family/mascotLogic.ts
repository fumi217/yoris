// キャラクター（家族のホームの右下。デザインの決めごと 12.4）の、画面に依らない決まり

/** 押してから、お問い合わせへ移るまでの時間（嬉しい顔を見せる。12.4） */
export const GO_DELAY_MS = 400

/** 押したときの行き先（下のメニューの「お問い合わせ」と同じ画面） */
export const INQUIRY_PATH = '/family/inquiry'

type ClickLike = {
  button: number
  metaKey: boolean
  ctrlKey: boolean
  shiftKey: boolean
  altKey: boolean
}

/**
 * ふつうの左クリックか。右クリック・Ctrl（Cmd）＋クリック・Shift＋クリックなどは、
 * 待たずに、ブラウザの動き（新しいタブで開くなど）に任せる（12.4）。
 */
export function isPlainClick(event: ClickLike): boolean {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
}

/** 画面の動きを減らす設定か（OS の「視差効果を減らす」。2.3.3・2.2.2）。 */
export function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/** 吹き出しの文（辞書のキー。出すたびに、どれかを選ぶ。デザインの決めごと 12.4 の「押せると分かるようにする」。#405） */
export const BUBBLE_KEYS = [
  'layout.mascot_bubble_1',
  'layout.mascot_bubble_2',
  'layout.mascot_bubble_3',
] as const

/** 画面を開いてから吹き出しを出すまで（0.8 秒）と、出している時間（5 秒。2.2.2） */
export const BUBBLE_DELAY_MS = 800
export const BUBBLE_SHOW_MS = 5000

// 同じブラウザのタブで 1 回だけ出す、の印の名前
const SEEN_KEY = 'yoris-mascot-bubble-seen'

/** 吹き出しの文を選ぶ（random は 0 以上 1 未満。テストでは決めた値を渡す）。 */
export function pickBubbleKey(random: number = Math.random()): (typeof BUBBLE_KEYS)[number] {
  const index = Math.min(BUBBLE_KEYS.length - 1, Math.floor(random * BUBBLE_KEYS.length))
  return BUBBLE_KEYS[index]
}

/** このタブで、もう吹き出しを出したか。sessionStorage が使えないときは、出していない扱い（出す）。 */
export function hasSeenBubble(): boolean {
  try {
    return window.sessionStorage.getItem(SEEN_KEY) === '1'
  } catch {
    return false
  }
}

/** 吹き出しを出したことを覚える（使えないときは、何もしない）。 */
export function markBubbleSeen(): void {
  try {
    window.sessionStorage.setItem(SEEN_KEY, '1')
  } catch {
    // 使えないときは、覚えられない（また出てもよい）
  }
}
