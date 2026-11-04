import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 開示設定の見た目（#452）。つまみを押すと保存の帯が出て、「元に戻す」で消えることを確かめる。
// 保存はしない（開発の DB の設定を変えない）。
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

for (const width of [617, 320]) {
  test(`幅 ${width}px：つまみで変えると保存の帯が出て、元に戻すと消える`, async ({ page }) => {
    await page.setViewportSize({ width, height: 824 })
    await loginAs(page, { kind: 'staff', role: 'director' })

    await page.goto('/admin/disclosure')
    const switches = page.getByRole('switch')
    await expect(switches.first()).toBeVisible()
    await expect(page.locator('main button[type="submit"]')).toHaveCount(0)

    await page.locator('label:has([role="switch"])').first().click()
    await expect(page.locator('main button[type="submit"]')).toBeVisible()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/admin-disclosure-${width}.png`, fullPage: true })

    // 「元に戻す」で、変更がなくなり、帯も消える（保存しない）
    await page.locator('main button[type="button"]', { hasText: /戻/ }).click()
    await expect(page.locator('main button[type="submit"]')).toHaveCount(0)
  })
}
