import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 職員の画面・管理画面の上の枠の、行き先のタブ（デザインの決めごと 8 章。#437）。
// 開発の DB をそのまま使う。読むだけで、何も作らない・変えない。

const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

test('職員の画面：タブが出て、今の画面のタブが選ばれ、押すと移れる', async ({ page }) => {
  await page.setViewportSize({ width: 820, height: 900 })
  await loginAs(page, { kind: 'staff', role: 'leader' })

  await page.goto('/staff')

  const nav = page.getByRole('navigation', { name: '職員の画面' })
  await expect(nav.getByRole('link')).toHaveCount(4)
  // 職員の画面は、漢字にふりがなが付く。文字ではなく、行き先で確かめる
  await expect(nav.locator('[aria-current="page"]')).toHaveAttribute('href', '/staff')

  await nav.locator('a[href="/staff/messages"]').click()
  await expect(page).toHaveURL(/\/staff\/messages/)
  await expect(nav.locator('[aria-current="page"]')).toHaveAttribute('href', '/staff/messages')
})

test('介護職員には、様子のメモの承認のタブを出さない', async ({ page }) => {
  await loginAs(page, { kind: 'staff', role: 'care_worker' })

  await page.goto('/staff')

  const nav = page.getByRole('navigation', { name: '職員の画面' })
  await expect(nav.getByRole('link')).toHaveCount(3)
})

test('管理画面：トップのタブが選ばれ、ほかの画面ではもとのタブが選ばれる', async ({ page }) => {
  await loginAs(page, { kind: 'staff', role: 'director' })

  await page.goto('/admin')
  const nav = page.getByRole('navigation', { name: '管理画面' })
  await expect(nav.locator('[aria-current="page"]')).toHaveAttribute('href', '/admin')

  await page.goto('/admin/visit-settings')
  await expect(nav.locator('[aria-current="page"]')).toHaveAttribute(
    'href',
    '/admin/visit-settings',
  )
})

test('タブレット（617×824）：上の段は 1 行で、タブはすべて画面の中に見える', async ({ page }) => {
  await page.setViewportSize({ width: 617, height: 824 })
  for (const [role, path, name] of [
    ['leader', '/staff', '職員の画面'],
    ['director', '/admin', '管理画面'],
  ] as const) {
    await loginAs(page, { kind: 'staff', role })
    await page.goto(path)
    const nav = page.getByRole('navigation', { name })
    await expect(nav).toBeVisible()
    for (const link of await nav.getByRole('link').all()) {
      const box = await link.boundingBox()
      expect(box && box.x >= 0 && box.x + box.width <= 617).toBeTruthy()
    }
    // 上の段（ロゴと名前のボタン）が 1 行に収まる：名前のボタンの上端が、ロゴの下端より上
    const logo = await page.getByRole('img', { name: 'YORIS' }).boundingBox()
    const account = await page.locator('button[aria-controls="staff-account-panel"]').boundingBox()
    expect(logo && account && account.y < logo.y + logo.height).toBeTruthy()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/tabs-617-${role}.png`, fullPage: false })
  }
})

test('名前のボタンで、言語とログアウトの段が開く', async ({ page }) => {
  await loginAs(page, { kind: 'staff', role: 'leader' })
  await page.goto('/staff')
  const panel = page.locator('#staff-account-panel')
  await expect(panel).toBeHidden()

  await page.locator('button[aria-controls="staff-account-panel"]').click()

  await expect(panel).toBeVisible()
  await expect(panel.getByRole('combobox')).toBeVisible()
})

for (const width of [320, 360]) {
  test(`幅 ${width}px：ページは横にスクロールしない（タブの帯だけが動く）`, async ({ page }) => {
    await page.setViewportSize({ width, height: 700 })
    await loginAs(page, { kind: 'staff', role: 'leader' })

    await page.goto('/staff')
    await expect(page.getByRole('navigation', { name: '職員の画面' })).toBeVisible()

    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/tabs-${width}.png`, fullPage: false })
  })
}
