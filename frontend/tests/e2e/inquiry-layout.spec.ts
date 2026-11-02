import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// お問い合わせの入力欄（下に固定。デザインの決めごと 13.5・PR #410）の、重なりと、すき間を測る。
// 単体テスト（Vitest）は、画面を動かせないので、ここで確かめる。開発の DB を読むだけで、何も作らない・変えない
// （「面会・予定について」は、AI を呼ばない用件のボタン。FR-001a）。

for (const height of [520, 800]) {
  test(`いちばん下までスクロールしても、最後の内容が入力欄の下に隠れず、入力欄は下のメニューの真上にある（高さ ${height}px）`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height })
    await loginAs(page, { kind: 'family', index: 0 })
    await page.goto('/family/inquiry')
    await page.getByRole('button', { name: /面会・予定について/ }).click()
    // 「アプリの案内」のカードが出る（会話の、いちばん下の内容になる）
    const guide = page.locator('[role="status"] >> text=/面会|予約/').first()
    await expect(guide).toBeVisible()

    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    await page.waitForTimeout(300)

    const box = await page.evaluate(() => {
      const form = document.querySelector('form')!.getBoundingClientRect()
      const nav = document.querySelector('nav')!.getBoundingClientRect()
      const card = document.querySelector('[role="status"]')!.getBoundingClientRect()
      return {
        formTop: form.top,
        formBottom: form.bottom,
        navTop: nav.top,
        cardBottom: card.bottom,
      }
    })

    // 入力欄の下端が、下のメニューの上端と、同じ位置（すき間も、重なりもない）
    expect(Math.abs(box.formBottom - box.navTop)).toBeLessThanOrEqual(1)
    // 最後の内容（アプリの案内）の下端が、入力欄の上端より上にある（隠れない）
    expect(box.cardBottom).toBeLessThanOrEqual(box.formTop)
  })
}
