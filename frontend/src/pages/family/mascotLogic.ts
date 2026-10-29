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
