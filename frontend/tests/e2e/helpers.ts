import { expect, type Page } from '@playwright/test'

type DevUser = {
  user_id: number
  kind: 'staff' | 'family'
  role: string | null
  display_name: string
}

// 書き込みの API には、このヘッダーが要る（spec 001 の research.md R-03・CSRF 対策）
const FETCH_HEADERS = { 'X-Requested-With': 'fetch' }

/**
 * 初期データの人としてログインした状態にする（開発用の切り替え。spec 001 の research.md R-02）。
 * 職員は役割で、家族は先頭の 1 人を選ぶ。`index` を付けると、同じ条件の人の何番目か（0 から）を選べる
 * （2 組の家族で試したいとき。`GET /api/dev/users` の順）。
 */
export async function loginAs(
  page: Page,
  who: { kind: 'family'; index?: number } | { kind: 'staff'; role: string; index?: number },
) {
  const res = await page.request.get('/api/dev/users')
  expect(res.ok()).toBeTruthy()
  const users = (await res.json()) as DevUser[]
  const user = users.filter(
    (u) => u.kind === who.kind && (who.kind === 'family' || u.role === who.role),
  )[who.index ?? 0]
  if (!user)
    throw new Error(`初期データに ${JSON.stringify(who)} の人がいません。seed を流しましたか`)
  const sw = await page.request.post('/api/dev/switch-user', {
    data: { user_id: user.user_id },
    headers: FETCH_HEADERS,
  })
  expect(sw.status()).toBe(204)
}
