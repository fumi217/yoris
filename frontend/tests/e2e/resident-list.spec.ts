import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 職員の入居者一覧（デザインの決めごと 11.4。#431）：今日の進み具合・記録のチップ・横にはみ出さないこと。
// 開発の DB をそのまま使う。読むだけで、何も作らない・変えない。

for (const [name, width, height] of [
  ['タブレット', 820, 1100],
  ['幅 320px', 320, 700],
] as const) {
  test(`${name}：進み具合と記録のチップが出て、横にスクロールしない`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    await loginAs(page, { kind: 'staff', role: 'leader' })

    await page.goto('/staff')

    const bar = page.getByRole('progressbar')
    await expect(bar).toBeVisible()
    const max = Number(await bar.getAttribute('aria-valuemax'))
    const now = Number(await bar.getAttribute('aria-valuenow'))
    expect(max).toBeGreaterThan(0)
    expect(now).toBeGreaterThanOrEqual(0)
    expect(now).toBeLessThanOrEqual(max)
    // 記録のチップは、✔ か － の記号と、読み上げ用の文を持つ
    await expect(
      page
        .locator('li')
        .getByText(/記録済み|まだ記録していません/)
        .first(),
    ).toBeAttached()
    // 画面の横幅からはみ出さない（1.4.10）
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/residents-${width}.png`, fullPage: true })
  })
}
