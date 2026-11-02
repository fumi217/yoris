import { expect, test, type Page } from '@playwright/test'
import { loginAs } from './helpers'

// spec 003 の quickstart.md「ミニマム版（User Story 1）の確認」の 1〜7（003-T036）。
// 予約 → 重なる時刻が選べない → 2 組で満員 → 同じ家族の 2 回目 → ログインしていないとき。
// 同時に予約したとき（8・9）と、ほかの家族の予約の取り消し（10）は、pytest で確かめる。
//
// 開発の DB をそのまま使うので、最初に面会の設定を初期の形（8 つの時刻・1 日 2 組）にし、
// 最後に元へ戻す。作った予約は、最後に家族が自分で取り消す（家族の取り消しはお知らせを作らない）。
// 予約したときの「予約が確定しました」のお知らせとメール（Mailpit）は残る。

const FETCH_HEADERS = { 'X-Requested-With': 'fetch' }

// 初期データの開始時刻の候補と、1 日に受け付ける組数（spec 003 の Assumptions）
const DEFAULT_SETTINGS = {
  daily_limit: 2,
  start_times: ['10:00', '10:30', '13:00', '13:30', '14:00', '14:30', '15:00', '15:30'],
}
const WEEKDAYS = ['日', '月', '火', '水', '木', '金', '土']

type Settings = { daily_limit: number; start_times: string[] }
type Day = {
  date: string
  closed: boolean
  mine: boolean
  start_times: { start_time: string; selectable: boolean }[]
}

/** 日本時間の今日から days 日あと（"YYYY-MM-DD"）。 */
function daysFromToday(days: number): string {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo' }).format(new Date())
  const value = new Date(`${today}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

/** 面会の画面の日付のボタンの名前（例：「10月30日（金）」。家族の画面はふりがななし）。 */
function dateLabel(date: string): string {
  const [, month, day] = date.split('-').map(Number)
  const weekday = WEEKDAYS[new Date(`${date}T00:00:00Z`).getUTCDay()]
  return `${month}月${day}日（${weekday}）`
}

/** 面会の画面を開き、その日のボタンが出る月まで「次の月」で進める。 */
async function openDay(page: Page, date: string) {
  await page.goto('/family/visits')
  await expect(page.getByRole('heading', { name: '面会の予約' })).toBeVisible()
  const dayButton = page.getByRole('button', { name: dateLabel(date) })
  for (let i = 0; i < 2 && (await dayButton.count()) === 0; i++) {
    await page.getByRole('button', { name: /次の月/ }).click()
  }
  return dayButton
}

async function myReservationIds(page: Page, date: string): Promise<number[]> {
  const res = await page.request.get('/api/family/visits')
  const rows = (await res.json()) as { id: number; visit_date: string; status: string }[]
  return rows.filter((row) => row.visit_date === date && row.status === 'booked').map((r) => r.id)
}

test('面会の予約：重なる時刻と 1 日 2 組を守り、同じ家族は 1 日 1 回まで（quickstart の 1〜7）', async ({
  page,
  browser,
}) => {
  // --- 準備：元の面会の設定を読む（最後に戻す。読めたあとは、どこで落ちても finally で戻す） ---
  await loginAs(page, { kind: 'staff', role: 'clerk' })
  const original = (await (await page.request.get('/api/admin/visit-settings')).json()) as Settings
  // 片付けで予約を取り消す日（決まる前に落ちたときは、予約の取り消しはしない）
  let cleanupDate: string | null = null

  try {
    // 面会の設定を初期の形にする
    const put = await page.request.put('/api/admin/visit-settings', {
      data: DEFAULT_SETTINGS,
      headers: FETCH_HEADERS,
    })
    expect(put.ok()).toBeTruthy()

    // 明後日から 4 週間先までで、休みでなく、どの時刻もまだ予約されていない最初の日を「その日」にする
    // （明日は、取り消しの締め切り（前の日の 17 時）に当たることがあるので使わない）
    // 家族 A の入居者の呼び名（家族 B の画面に出ないことを確かめる）
    const users = (await (await page.request.get('/api/dev/users')).json()) as {
      kind: string
      display_name: string
    }[]
    const familyAName = users.filter((user) => user.kind === 'family')[0].display_name

    await loginAs(page, { kind: 'family', index: 0 })
    const availability = (await (
      await page.request.get(
        `/api/family/visits/availability?from=${daysFromToday(2)}&to=${daysFromToday(28)}`,
      )
    ).json()) as { days: Day[] }
    const target = availability.days.find(
      (day) =>
        !day.closed &&
        day.start_times.length === DEFAULT_SETTINGS.start_times.length &&
        day.start_times.every((slot) => slot.selectable),
    )
    if (!target)
      throw new Error('空いている日がありません（開発の DB の予約・休みの日を確かめてください）')
    const date = target.date
    cleanupDate = date

    await test.step('1・2. 家族 A が、その日の 10:30 を 2 人で予約する', async () => {
      const dayButton = await openDay(page, date)
      await dayButton.click()
      // 開始時刻 8 つが出る
      await expect(page.getByRole('button', { name: /^\d{2}:\d{2}〜\d{2}:\d{2}$/ })).toHaveCount(8)
      await page.getByRole('button', { name: '10:30〜12:00' }).click()
      await page.getByRole('button', { name: '人数を増やす' }).click()
      await page.getByRole('button', { name: '予約する' }).click()

      await expect(page.getByRole('heading', { name: '予約が確定しました' })).toBeVisible()
      await expect(page.getByText(/10:30〜12:00/).first()).toBeVisible()
      await expect(page.getByText(/2人/).first()).toBeVisible()
    })

    await test.step('6. 家族 A には、その日が「予約済み」で、API で送っても 409（その日がまだ 1 組のうちに確かめる）', async () => {
      // 2 組に達したあとは、1 日の組数の確かめ（visit_day_full）が先に返るので、家族 B の予約の前に確かめる
      const dayButton = await openDay(page, date)
      await expect(dayButton).toBeDisabled()
      // マスの中では、2 行（「予約／済み」）に折れる。改行を挟んでも、同じ言葉として確かめる（#407）
      await expect(dayButton).toContainText(/予約\s*済み/)

      const again = await page.request.post('/api/family/visits', {
        data: { visit_date: date, start_time: '15:00', party_size: 1 },
        headers: FETCH_HEADERS,
      })
      expect(again.status()).toBe(409)
      expect((await again.json()).error.code).toBe('visit_already_booked_day')
    })

    await test.step('3. 家族 B には、10:30〜12:00 と重なる 10:00・10:30 が選べない', async () => {
      await loginAs(page, { kind: 'family', index: 1 })
      const dayButton = await openDay(page, date)
      await dayButton.click()

      await expect(page.getByRole('button', { name: '10:00〜11:30' })).toBeDisabled()
      await expect(page.getByRole('button', { name: '10:30〜12:00' })).toBeDisabled()
      await expect(page.getByRole('button', { name: '13:00〜14:30' })).toBeEnabled()
      // ほかの家族の名前・入居者名は出ない（選べない理由も出さない）
      // （右下の開発用のユーザー切り替えには全員の名前があるので、画面の本体だけを見る）
      await expect(page.getByRole('main').getByText(familyAName)).toHaveCount(0)
    })

    await test.step('4. 家族 B が 13:00 を予約する（その日は 2 組）', async () => {
      await page.getByRole('button', { name: '13:00〜14:30' }).click()
      await page.getByRole('button', { name: '予約する' }).click()
      await expect(page.getByRole('heading', { name: '予約が確定しました' })).toBeVisible()
    })

    await test.step('5. 家族 C には、その日が「空きなし」で選べない（1 日 2 組に達した）', async () => {
      await loginAs(page, { kind: 'family', index: 2 })
      const dayButton = await openDay(page, date)
      await expect(dayButton).toBeDisabled()
      await expect(dayButton).toContainText(/空き\s*なし/)
    })

    await test.step('7. ログインしていないと、ログインの画面に案内される', async () => {
      const guest = await browser.newContext()
      const guestPage = await guest.newPage()
      await guestPage.goto('/family/visits')
      await expect(guestPage).toHaveURL(/\/login/)
      await guest.close()
    })
  } finally {
    // --- 片付け：家族 A・B が自分の予約を取り消し、面会の設定を元に戻す ---
    // 失敗しても止めずに続け、気づけるように出す（PR #281 ようこ）
    if (cleanupDate !== null) {
      for (const index of [0, 1]) {
        await loginAs(page, { kind: 'family', index })
        for (const id of await myReservationIds(page, cleanupDate)) {
          const cancelled = await page.request.delete(`/api/family/visits/${id}`, {
            headers: FETCH_HEADERS,
          })
          if (!cancelled.ok())
            console.warn(`片付け：予約 ${id} を取り消せませんでした（${cancelled.status()}）`)
        }
      }
    }
    await loginAs(page, { kind: 'staff', role: 'clerk' })
    const restored = await page.request.put('/api/admin/visit-settings', {
      data: {
        daily_limit: original.daily_limit,
        start_times: original.start_times.map((time) => time.slice(0, 5)),
      },
      headers: FETCH_HEADERS,
    })
    if (!restored.ok())
      console.warn(`片付け：面会の設定を元に戻せませんでした（${restored.status()}）`)
  }
})
