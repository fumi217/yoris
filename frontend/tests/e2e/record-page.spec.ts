import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 職員の記録の画面（デザインの決めごと 11.5。#439）：今日の記録の札・お皿の絵・顔の絵と、横にはみ出さないこと。
// 開発の DB をそのまま使う。読むだけで、何も作らない・変えない（記録は押さない）。

async function openFirstResident(page: import('@playwright/test').Page) {
  await page.goto('/staff')
  await page.locator('a[href^="/staff/residents/"]').first().click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}

for (const [name, width, height] of [
  ['タブレット 617×824', 617, 824],
  ['幅 320px', 320, 700],
] as const) {
  test(`${name}：今日の記録の札と、記録のボタンが出て、横にスクロールしない`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    await loginAs(page, { kind: 'staff', role: 'care_worker' })

    await openFirstResident(page)

    // 札は 5 つ（朝・昼・夜・機嫌・眠り）
    await expect(page.locator('ul.grid-cols-5 > li')).toHaveCount(5)
    // 食事 6 ＋ 機嫌 3 ＋ 眠り 3 のボタン
    await expect(page.locator('button[aria-pressed]')).toHaveCount(12)
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/record-${width}.png`, fullPage: true })
  })
}

test('「今日の記録」の夜の札を押すと、食事の夜ごはんが開く', async ({ page }) => {
  await loginAs(page, { kind: 'staff', role: 'care_worker' })
  await openFirstResident(page)

  await page.locator('ul.grid-cols-5 > li').nth(2).getByRole('button').click()

  await expect(page.getByRole('tab', { selected: true })).toContainText(/夜/)
})
