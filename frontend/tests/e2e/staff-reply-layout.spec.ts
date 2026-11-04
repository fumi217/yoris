import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 職員の返事・連絡帳の見返しの見た目（#457）。返事待ちの API は見本のデータに差し替える
// （開発の DB に返事待ちがなくても確かめられるように）。何も送らない・変えない。
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

for (const width of [617, 320]) {
  test(`幅 ${width}px：返事の画面と見返しの画面が、横にスクロールせずに出る`, async ({ page }) => {
    await page.setViewportSize({ width, height: 824 })
    await loginAs(page, { kind: 'staff', role: 'care_worker' })
    await page.goto('/staff')
    const href = await page.locator('a[href^="/staff/residents/"]').first().getAttribute('href')
    const id = href?.split('/')[3]
    await page.route(new RegExp(`/api/staff/residents/${id}/requests$`), (route) =>
      route.fulfill({
        json: {
          requests: [
            {
              id: 1,
              theme_code: 'theme.meals',
              theme_emoji: '',
              created_at: '2026-11-02T09:40:00Z',
              days: 1,
              templates: [
                { id: 11, code: 'template.meals.well' },
                { id: 12, code: 'template.meals.favorite' },
              ],
            },
          ],
          waiting_messages: 0,
        },
      }),
    )

    await page.goto(`/staff/residents/${id}/requests`)
    const choice = page.locator('main button[aria-pressed]').first()
    await choice.click()
    await expect(choice).toHaveAttribute('aria-pressed', 'true')
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/reply-${width}.png`, fullPage: true })

    await page.goto(`/staff/residents/${id}/contact-book`)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/staff-book-${width}.png`, fullPage: true })
  })
}
