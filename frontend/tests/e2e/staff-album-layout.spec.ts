import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 職員の写真を載せる画面の見た目（#461）。写真は送らない（開発の DB を変えない）。
// 1×1 の PNG（架空の画像）を「選ぶ」だけで、選んだ写真の行・ひとこと欄・「送る」を確かめる。
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
)
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

for (const width of [617, 320]) {
  test(`幅 ${width}px：選んだ写真が 1 行ずつ出て、横にスクロールしない`, async ({ page }) => {
    await page.setViewportSize({ width, height: 824 })
    await loginAs(page, { kind: 'staff', role: 'care_worker' })
    await page.goto('/staff')
    const href = await page.locator('a[href^="/staff/residents/"]').first().getAttribute('href')
    const id = href?.split('/')[3]

    await page.goto(`/staff/residents/${id}/album`)
    await page
      .locator('input[type="file"][multiple]')
      .setInputFiles([{ name: 'a.png', mimeType: 'image/png', buffer: PNG }])

    await expect(page.locator('main ul li img').first()).toBeVisible()
    await expect(page.locator('main input[type="text"]')).toBeVisible()
    await expect(page.getByRole('button', { name: /^送/ })).toBeVisible()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/album-staff-${width}.png`, fullPage: true })
  })
}
