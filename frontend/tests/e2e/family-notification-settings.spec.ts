import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 家族の「通知の設定」の見た目（デザインの決めごと 13.6。#449）。保存はしない（API を呼ばない）。
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

for (const width of [360, 320]) {
  test(`幅 ${width}px：つまみで切り替えると、下に保存の帯が出る。横にスクロールしない`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 740 })
    await loginAs(page, { kind: 'family', index: 0 })

    await page.goto('/family/settings')
    const switches = page.getByRole('switch')
    await expect(switches.first()).toBeVisible()
    await expect(page.getByRole('button', { name: '保存する' })).toHaveCount(0)

    // つまみ（見た目は span、押すのは行のラベル）を押すと、変更の帯が出る
    await page.locator('label:has([role="switch"])').first().click()
    const save = page.getByRole('button', { name: '保存する' })
    await expect(save).toBeVisible()
    // 帯は、下のメニューの上にある（重ならない）
    const saveBox = await save.boundingBox()
    const menuBox = await page.getByRole('navigation').last().boundingBox()
    expect(saveBox && menuBox && saveBox.y + saveBox.height <= menuBox.y).toBeTruthy()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/family-settings-${width}.png`, fullPage: false })
  })
}
