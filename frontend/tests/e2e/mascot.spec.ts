import { expect, test, type Page } from '@playwright/test'
import { loginAs } from './helpers'

// 家族のホームの右下のキャラクター（デザインの決めごと 12.4。#339）。
// 単体テスト（Vitest）は、画面を動かせない（jsdom を入れていない）ので、押したときの動きはここで確かめる。
// 開発の DB をそのまま使う。読むだけで、何も作らない・変えない。

const HOME = '/family'
const INQUIRY = '/family/inquiry'

async function openHome(page: Page) {
  await page.goto(HOME)
  await expect(mascot(page)).toBeVisible()
}

const mascot = (page: Page) => page.locator('[data-mascot] a')
// 2 枚目が嬉しい顔。見えていないときは opacity-0
const happyFace = (page: Page) => page.locator('[data-mascot] img').nth(1)

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 })
  await loginAs(page, { kind: 'family', index: 0 })
})

test('押すと嬉しい顔になり、少し待ってからお問い合わせへ移る', async ({ page }) => {
  await openHome(page)

  await mascot(page).click()

  // 押した直後は、まだホームのまま、嬉しい顔
  await expect(happyFace(page)).not.toHaveClass(/opacity-0/)
  expect(new URL(page.url()).pathname).toBe(HOME)
  await page.waitForURL(`**${INQUIRY}`)
})

test('Space でも押せる', async ({ page }) => {
  await openHome(page)

  await mascot(page).focus()
  await page.keyboard.press('Space')

  await page.waitForURL(`**${INQUIRY}`)
})

test('続けて押しても、移るのは 1 回だけ', async ({ page }) => {
  await openHome(page)

  await mascot(page).click()
  await mascot(page).click()
  await mascot(page).click()
  await page.waitForURL(`**${INQUIRY}`)

  // 1 回だけ移ったので、1 回の「戻る」でホームに戻る
  await page.goBack()
  await page.waitForURL(`**${HOME}`)
})

test('移った直後に戻っても、ふつうの顔で、もう一度押せる（PR #340）', async ({ page }) => {
  await openHome(page)

  // 移った直後に戻ると、移動が取りやめになり、キャラクターが作り直されないことがある
  // （起きる割合がそろわないので、何度か繰り返す）
  for (let i = 0; i < 20; i++) {
    await mascot(page).click()
    await page.waitForURL(`**${INQUIRY}`)
    await page.goBack()
    await page.waitForURL(`**${HOME}`)
    await expect(happyFace(page)).toHaveClass(/opacity-0/)
  }
  await mascot(page).click()
  await page.waitForURL(`**${INQUIRY}`)
})

test('「動きを減らす」設定では、動かさず、待たずに移る', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openHome(page)

  const animation = await page
    .locator('.mascot-float')
    .evaluate((element) => getComputedStyle(element).animationName)
  expect(animation).toBe('none')

  await mascot(page).click()
  // 待たずに移るので、嬉しい顔にはならない
  await page.waitForURL(`**${INQUIRY}`, { timeout: 300 })
})
