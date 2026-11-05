import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 面会の設定の見た目（#453）。時刻の札を押すと保存の帯が出て、「元に戻す」で消えることを確かめる。
// 保存はしない（開発の DB の設定を変えない）。
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

for (const width of [617, 320]) {
  test(`幅 ${width}px：時刻の札で変えると保存の帯が出て、元に戻すと消える`, async ({ page }) => {
    await page.setViewportSize({ width, height: 824 })
    await loginAs(page, { kind: 'staff', role: 'director' })

    await page.goto('/admin/visit-settings')
    // 開始時刻と組数のフォーム（お休みの日のフォームとは別）
    const settings = page.locator('main form:has(input[type="checkbox"])')
    const first = page.locator('main label:has(input[type="checkbox"])').first()
    await expect(first).toBeVisible()
    await expect(settings.locator('button[type="submit"]')).not.toBeVisible()

    await first.click()
    await expect(settings.locator('button[type="submit"]')).toBeVisible()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({
        path: `test-results/admin-visit-settings-${width}.png`,
        fullPage: true,
      })

    await settings.locator('button[type="button"]', { hasText: /戻/ }).click()
    await expect(settings.locator('button[type="submit"]')).not.toBeVisible()
  })
}
