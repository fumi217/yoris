import { addDays } from './visits/visitDates'

// 家族のアルバムの画面で使う、型と小さな関数（spec 005 の 005-T012。contracts の「家族」）。

export type AlbumPhoto = {
  id: number
  posted_at: string
  // 職員が自由に書いた文。辞書を通さず、HTML として解釈せず、文字としてだけ出す
  comment: string | null
  // 写真のファイル（GET /api/files/{id}）
  url: string
}

/** 載せた日（日本時間）ごとの写真。API が、新しい順に返す。 */
export type AlbumDay = { date: string; photos: AlbumPhoto[] }

/** GET /api/family/album の返り値。next_before が空なら、続きはない。 */
export type AlbumPage = { days: AlbumDay[]; next_before: number | null }

/** GET /api/family/features の返り値（開示設定の機能の状態）。 */
export type FamilyFeatures = { album: boolean }

/**
 * 何ページかを、日ごとにつなぐ。ページの境目で同じ日が続くときは、1 つの日にまとめる
 * （1 日の途中でページが切れても、日の見出しが 2 つに割れないように）。
 */
export function mergeAlbumPages(pages: AlbumPage[]): AlbumDay[] {
  const days: AlbumDay[] = []
  for (const page of pages) {
    for (const day of page.days) {
      const last = days[days.length - 1]
      if (last && last.date === day.date) {
        last.photos = [...last.photos, ...day.photos]
      } else {
        days.push({ date: day.date, photos: [...day.photos] })
      }
    }
  }
  return days
}

/** 日付（"2026-11-05"）を、見出しに出す月と日にする（日本時間の日付をそのまま使う）。 */
export function dayParts(date: string): { month: string; day: string } {
  const [, month = '', day = ''] = date.split('-')
  return { month: String(Number(month)), day: String(Number(day)) }
}

/** 続きを読むときの `before`（最後のページの next_before）。続きがなければ undefined。 */
export function nextBefore(lastPage: AlbumPage): number | undefined {
  return lastPage.next_before ?? undefined
}

/** 日の見出しの種類：今日・昨日・それ以外（日付と曜日）。today は日本時間の今日（"2026-10-30"）。 */
export type DayKind = 'today' | 'yesterday' | 'other'

export function dayKindOf(date: string, today: string): DayKind {
  if (date === today) return 'today'
  return date === addDays(today, -1) ? 'yesterday' : 'other'
}
