import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'
const row = (
  id: number,
  name: string,
  rel: string,
  category: string,
  summary: string,
  status: string,
  days: number,
  late: boolean,
  assignee: string | null,
) => ({
  id,
  resident_id: id,
  resident_display_name: name,
  resident_display_name_ruby: name,
  family_relationship: rel,
  category,
  assignee: assignee ? { id: 1, display_name: assignee } : null,
  summary,
  summary_ruby: summary,
  status,
  handed_at: '2026-11-01T01:00:00Z',
  elapsed_days: days,
  waiting_over_a_day: late,
})
const rows = [
  row(
    1,
    '山田 花子',
    'daughter',
    'medical',
    'このごろ食欲が落ちていると聞きました。様子を知りたい。',
    'waiting',
    2,
    true,
    null,
  ),
  row(
    2,
    '鈴木 一郎',
    'son',
    'care_request',
    '面会のときに、孫を連れて行ってよいか。',
    'waiting',
    0,
    false,
    '伊藤',
  ),
]
const detail = {
  ...rows[0],
  origin: {
    id: 1,
    sender: 'family',
    body: 'このごろ食欲が落ちていると聞きました。様子を知りたいです。',
    created_at: '2026-11-01T01:00:00Z',
    template_codes: null,
    note: null,
  },
  origin_ruby:
    'このごろ{食欲|しょくよく}が{落|お}ちていると{聞|き}きました。{様子|ようす}を{知|し}りたいです。',
  previous: [
    {
      id: 2,
      sender: 'ai',
      body: '体調のことは、職員がお答えします。職員に伝えました。',
      created_at: '2026-11-01T01:01:00Z',
      template_codes: null,
      note: null,
    },
  ],
  follow_ups: [],
  templates: [
    { id: 1, code: 'staff_template.medical.call' },
    { id: 2, code: 'staff_template.medical.nurse' },
  ],
}
// 家族からのメッセージ（一覧・詳細）の見た目（デザインの決めごと 11.1。#441）。
// API は見本のデータに差し替える（開発の DB にメッセージがなくても確かめられるように）。何も作らない・変えない。
const overflow = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

for (const w of [617, 320]) {
  test(`幅 ${w}px：一覧と詳細が、横にスクロールせずに出る`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: 824 })
    await loginAs(page, { kind: 'staff', role: 'director' })
    // 一覧（`/api/staff/messages?status=…`）と詳細（`/api/staff/messages/1`）に、それぞれだけ当たる形で差し替える
    // （登録の順や、URL の範囲の重なりに頼らない。PR #444 の AI チューター）
    await page.route(/\/api\/staff\/messages\?/, (r) => r.fulfill({ json: { messages: rows } }))
    await page.route(/\/api\/staff\/messages\/1$/, (r) => r.fulfill({ json: detail }))
    await page.goto('/staff/messages')
    await expect(page.locator('a[href="/staff/messages/1"]')).toBeVisible()
    // 対応待ちの行は、左の線（色だけでなく、タブと「担当」の文字でも分かる）
    await expect(page.locator('a[href="/staff/messages/1"]')).toHaveClass(/inset_4px/)
    expect(await overflow(page)).toBeLessThanOrEqual(0)

    await page.goto('/staff/messages/1')
    // 選んだ定型文は aria-pressed で伝わる
    const template = page.locator('button[aria-pressed]').first()
    await template.click()
    await expect(template).toHaveAttribute('aria-pressed', 'true')
    expect(await overflow(page)).toBeLessThanOrEqual(0)
    if (process.env.SHOT)
      await page.screenshot({ path: `test-results/msg-detail-${w}.png`, fullPage: true })
  })
}
