// 「2 回押して決める」ボタン（ConfirmButton）の時間の決まり。
// 押し間違いで取り消さないよう、1 回目のあとすぐの 2 回目は受け付けない。
// 時間がたっても元には戻さない（「やめる」か 2 回目を押すまで残す。時間の制限（WCAG 2.2.1）をなくす。#300）

// 1 回目から、この時間がたつまでは 2 回目を受け付けない（素早い 2 回のタップで、確かめずに決まらないように）
export const CONFIRM_MIN_MS = 500

/** 2 回目を受け付けるか。firstAt は 1 回目に押した時刻（ミリ秒）。 */
export function canConfirm(firstAt: number, now: number): boolean {
  return now - firstAt >= CONFIRM_MIN_MS
}
