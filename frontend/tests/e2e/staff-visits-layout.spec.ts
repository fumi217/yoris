import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 面会の今日の予定・予約の一覧の見た目（#443）。API は見本のデータに差し替える（予約がなくても確かめられるように）。
// 何も作らない・変えない（取り消しは押さない）。
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

const reservation = (
  id: number,
  date: string,
  start: string,
  status: string,
  reason: string | null,
) => ({
  id,
  resident_id: id,
  resident_name: '山田 花子',
  resident_name_ruby: '山田 花子',
  room: '203',
  visit_date: date,
  start_time: start,
  party_size: 2,
  status,
  cancel_reason: reason,
  created_at: '2026-10-30T01:00:00Z',
})

for (const width of [617, 320]) {
  test(`幅 ${width}px：今日の予定と予約の一覧が、横にスクロールせずに出る`, async ({ page }) => {
    await page.setViewportSize({ width, height: 824 })
    await loginAs(page, { kind: 'staff', role: 'leader' })
    const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo' }).format(new Date())
    const rows = [
      reservation(1, today, '10:00:00', 'booked', null),
      reservation(2, today, '14:00:00', 'cancelled_by_staff', '館内の行事のため'),
    ]
    await page.route('**/api/staff/visits/today', (route) => route.fulfill({ json: [rows[0]] }))
    await page.route('**/api/admin/visits?*', (route) => route.fulfill({ json: rows }))

    await page.goto('/staff/visits/today')
    await expect(page.locator('ol > li')).toHaveCount(1)
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/visits-today-${width}.png`, fullPage: true })

    await page.goto('/staff/visits')
    // 取り消せるのは、予約済みの 1 件だけ（職員の画面はふりがなが付くので、ボタンの数で確かめる）
    await expect(page.locator('main li button')).toHaveCount(1)
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/visits-list-${width}.png`, fullPage: true })
  })
}
