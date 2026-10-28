import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// quickstart.md「ぶつかる場面の確認」：家族アカウントで、職員の画面の URL を直接開く → 開けない（US1・FR-024）
test.describe('家族は職員の画面を開けない', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, { kind: 'family' })
  })

  test('職員の画面の URL を直接開くと、家族の画面に戻される', async ({ page }) => {
    await page.goto('/staff')
    await expect(page).toHaveURL(/\/family$/)
  })

  test('管理画面の URL を直接開いても、家族の画面に戻される', async ({ page }) => {
    await page.goto('/admin')
    await expect(page).toHaveURL(/\/family$/)
  })

  test('職員の API を直接呼んでも、読めない（403）', async ({ page }) => {
    const res = await page.request.get('/api/staff/residents')
    expect(res.status()).toBe(403)
  })
})
