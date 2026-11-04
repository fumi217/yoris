import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// 様子のメモの承認・書く画面の見た目（#442）。承認の一覧の API は見本のデータに差し替える
// （開発の DB に承認待ちがなくても確かめられるように）。何も作らない・変えない（ボタンは押さない）。
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

const approval = {
  id: 1,
  resident_id: 1,
  resident_name: '山田 花子',
  resident_name_ruby: '山田 花子',
  author_name: 'シティ',
  is_own: false,
  memo_date: '2026-10-31',
  written_at: '2026-10-31T07:20:00Z',
  source_lang: 'id',
  original_text: 'Waktu snack sore, beliau ngobrol dengan teman dan terlihat senang.',
  rewritten_text: '午後のおやつの時間に、お友だちと楽しそうにお話しされていました。',
  back_translation: 'Pada waktu snack sore, beliau mengobrol dengan teman dengan senang.',
  warnings: ['length_changed'],
  status: 'pending',
  confirmed_at: '2026-10-31T07:30:00Z',
  approved_at: null,
  waiting_minutes: 60 * 26,
  overdue: true,
}

for (const width of [617, 320]) {
  test(`幅 ${width}px：承認の画面と書く画面が、横にスクロールせずに出る`, async ({ page }) => {
    await page.setViewportSize({ width, height: 824 })
    await loginAs(page, { kind: 'staff', role: 'leader' })
    await page.route('**/api/staff/memo-approvals?*', (route) =>
      route.fulfill({ json: [approval] }),
    )

    await page.goto('/staff/memo-approvals')
    await expect(page.getByRole('article')).toBeVisible()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/memo-approvals-${width}.png`, fullPage: true })

    // 書く画面も、入居者と自分のメモの API を差し替える（開発の DB の入居者に頼らない。PR #445 の AI チューター）
    await page.route(/\/api\/staff\/residents\/99\/contact-book$/, (route) =>
      route.fulfill({
        json: {
          date: '2026-11-03',
          resident: {
            id: 99,
            display_name: '山田 花子',
            display_name_ruby: '山田 花子',
            room: '203',
          },
          records: [],
          replies: [],
        },
      }),
    )
    await page.route(/\/api\/staff\/memos\?resident_id=99$/, (route) => route.fulfill({ json: [] }))
    await page.goto('/staff/residents/99/memos/new')
    // 手順 1（様子を書く）の面が出る
    await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible()
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/memo-editor-${width}.png`, fullPage: true })
  })
}
