import { expect, test, type Locator } from '@playwright/test'
import { loginAs } from './helpers'

// ボタンの影と押したときの動き（デザインの決めごと 7 章。#377）。
// 単体テスト（Vitest）は CSS を読めないので、画面で確かめる。読むだけで、何も作らない・変えない。

const shadowOf = (button: Locator) =>
  button.evaluate((element) => getComputedStyle(element).boxShadow)
const transformOf = (button: Locator) =>
  button.evaluate((element) => getComputedStyle(element).transform)

// 影が見えるか。Tailwind の \`shadow-*\`（透明の層だけの影）が付いたボタンは、'none' ではなく、透明の影が返るので、
// 色の濃さ（アルファ）が 0 のものしかないときは、影がない、と見なす
const hasVisibleShadow = (value: string) =>
  value !== 'none' && /rgba?\([^)]*\)/g.test(value) && !onlyTransparent(value)
function onlyTransparent(value: string): boolean {
  const colors = value.match(/rgba?\([^)]*\)/g) ?? []
  return colors.every((color) => /,\s*0\)$/.test(color) || color.includes('/ 0)'))
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 })
  await loginAs(page, { kind: 'family', index: 0 })
  await page.goto('/family/inquiry')
})

test('背景か枠のあるボタンには影が付く。押せないボタンには付かない', async ({ page }) => {
  // 用件の選択肢（枠のあるボタン）
  const choice = page.getByRole('button', { name: '面会・予定について' })
  expect(hasVisibleShadow(await shadowOf(choice))).toBe(true)

  // 何も書いていないときの、送るボタン（押せない）
  const send = page.getByRole('button', { name: '送る' })
  await expect(send).toBeDisabled()
  expect(hasVisibleShadow(await shadowOf(send))).toBe(false)
})

test('押している間は、影が消えて 1px 下がる', async ({ page }) => {
  const choice = page.getByRole('button', { name: 'その他のご質問' })
  const box = await choice.boundingBox()
  await page.mouse.move(box!.x + 8, box!.y + 8)
  await page.mouse.down()

  // 押している間は、画面ごとに \`shadow-sm\` がある用件のボタンでも、影が消える
  expect(hasVisibleShadow(await shadowOf(choice))).toBe(false)
  expect(await transformOf(choice)).toBe('matrix(1, 0, 0, 1, 0, 1)')
  await page.mouse.up()
})

test('「動きを減らす」設定では、押しても下がらない（影は消える）', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const choice = page.getByRole('button', { name: 'その他のご質問' })
  const box = await choice.boundingBox()
  await page.mouse.move(box!.x + 8, box!.y + 8)
  await page.mouse.down()

  expect(await transformOf(choice)).toBe('none')
  await page.mouse.up()
})
