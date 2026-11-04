import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 管理画面のトップ（今日の状況。#451）。メッセージと今日の面会の API は見本のデータに差し替える
// （開発の DB に、対応待ちや今日の予約がなくても確かめられるように）。何も作らない・変えない。
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

const message = (id: number, late: boolean) => ({
  id,
  resident_id: id,
  resident_display_name: '山田 花子',
  resident_display_name_ruby: '山田 花子',
  family_relationship: 'daughter',
  category: 'medical',
  assignee: null,
  summary: '食欲のこと',
  summary_ruby: '食欲のこと',
  status: 'waiting',
  handed_at: '2026-11-02T01:00:00Z',
  elapsed_days: late ? 2 : 0,
  waiting_over_a_day: late,
})

for (const width of [617, 320]) {
  test(`幅 ${width}px：今日の状況の数と一覧が出て、横にスクロールしない`, async ({ page }) => {
    await page.setViewportSize({ width, height: 824 })
    await loginAs(page, { kind: 'staff', role: 'director' })
    await page.route(/\/api\/staff\/messages\?/, (route) =>
      route.fulfill({ json: { messages: [message(1, true), message(2, false)] } }),
    )
    await page.route(/\/api\/staff\/messages\/count$/, (route) =>
      route.fulfill({ json: { count: 2 } }),
    )
    await page.route(/\/api\/staff\/visits\/today$/, (route) =>
      route.fulfill({
        json: [
          {
            id: 1,
            resident_id: 1,
            resident_name: '鈴木 一郎',
            resident_name_ruby: '鈴木 一郎',
            room: '205',
            visit_date: '2026-11-04',
            start_time: '14:00:00',
            party_size: 1,
            status: 'booked',
            cancel_reason: null,
            created_at: '2026-11-01T01:00:00Z',
          },
        ],
      }),
    )

    await page.goto('/admin')
    await expect(page.locator('main a[href="/admin/messages/1"]')).toBeVisible()
    // 施設長には、見せていない項目の札（開示設定へ）も出る
    await expect(page.locator('main a[href="/admin/disclosure"]').first()).toBeVisible()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/admin-home-${width}.png`, fullPage: true })
  })
}

test('事務員には、見せていない項目の札を出さない（開示設定を開けないため）', async ({ page }) => {
  await loginAs(page, { kind: 'staff', role: 'clerk' })

  await page.goto('/admin')

  await expect(page.locator('main a[href="/admin/messages"]').first()).toBeVisible()
  await expect(page.locator('main a[href="/admin/disclosure"]')).toHaveCount(0)
})
