import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test'
import { loginAs } from './helpers'

// spec 005 の quickstart.md「載せる・見る」「削除」の 1〜14（005-T033）。
// 職員が載せる → 家族 A が見る → 家族 B には見えない → 削除する。
// 抜かすもの：2 の「4 タップ以内・30 秒」（人が確かめる）、6 の縦向きの写真（実機）、7（確認はやめた）。
//
// 開発の DB をそのまま使う。写真の数ではなく、このテストが付けた固有のコメントで確かめる
// （手で載せた写真・初期データの写真があっても通る）。
// 載せた写真は、最後（落ちたときも）に職員の API で削除する。ファイルと uploaded_files の行は消えるが、
// album_photos の行は「削除した記録」として残る（アプリの決まり）。
// 削除したあとのファイルの URL は、ブラウザのキャッシュ（5 分）を使わない page.request で確かめる。

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
const FETCH_HEADERS = { 'X-Requested-With': 'fetch' }

// 1×1 の PNG（架空の画像）
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
)
// 名前だけ .jpg の PDF（quickstart の 4）
const PDF_NAMED_JPG = {
  name: 'photo.jpg',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4\n%fake\n'),
}

type Photo = { id: number; comment: string | null; url: string }
type StaffAlbum = { family_visible: boolean; photos: Photo[] }
type Residents = { residents: { id: number; display_name: string }[] }

async function staffAlbum(request: APIRequestContext, residentId: number): Promise<StaffAlbum> {
  const res = await request.get(`/api/staff/residents/${residentId}/album`)
  expect(res.status()).toBe(200)
  return (await res.json()) as StaffAlbum
}

async function newPage(browser: Browser): Promise<Page> {
  const context = await browser.newContext({
    baseURL: BASE_URL,
    viewport: { width: 420, height: 900 },
  })
  return context.newPage()
}

test('アルバム：載せる → 家族 A が見る → 家族 B には見えない → 削除する（quickstart の 1〜14）', async ({
  browser,
}) => {
  test.setTimeout(120_000)
  const comment = `E2E の確認 ${Date.now()}`
  const staff = await newPage(browser)
  const familyA = await newPage(browser)
  const familyB = await newPage(browser)
  const anonymous = await newPage(browser)
  const created: number[] = []

  try {
    await loginAs(staff, { kind: 'staff', role: 'care_worker' })
    await loginAs(familyA, { kind: 'family', index: 0 })
    await loginAs(familyB, { kind: 'family', index: 1 })

    // 入居者 A（家族 A の入居者）を、家族 A の表示名から見つける
    const me = (await (await familyA.request.get('/api/me')).json()) as { display_name: string }
    const residents = (await (await staff.request.get('/api/staff/residents')).json()) as Residents
    const resident = residents.residents.find((r) => r.display_name === me.display_name)
    if (!resident)
      throw new Error('家族 A の入居者が、職員の一覧に見つかりません。seed を流しましたか')
    const before = new Set((await staffAlbum(staff.request, resident.id)).photos.map((p) => p.id))

    // --- 1：「写真を載せる」を開く。「撮る」と「写真から選ぶ」が出る ---
    await staff.goto(`/staff/residents/${resident.id}/album`)
    await expect(staff.locator('input[type="file"]')).toHaveCount(2)
    await expect(staff.locator('input[type="file"][capture]')).toHaveCount(1)

    // --- 4：名前だけ .jpg の PDF は、載せられない（送る前に断る） ---
    await staff.locator('input[type="file"][multiple]').setInputFiles(PDF_NAMED_JPG)
    await expect(staff.getByText(/JPG か PNG/).first()).toBeVisible()
    // 「送る」は出るが、断った写真だけでは押せない
    await expect(staff.getByRole('button', { name: /^送/ })).toBeDisabled()
    await staff.reload()

    // --- 2・3：コメントなし 1 枚と、コメント付き 1 枚を、1 回で載せる ---
    await staff.locator('input[type="file"][multiple]').setInputFiles([
      { name: 'one.png', mimeType: 'image/png', buffer: PNG },
      { name: 'two.png', mimeType: 'image/png', buffer: PNG },
    ])
    // 100 文字を超える入力は、入力欄が止める
    const commentInputs = staff.locator('input[type="text"]')
    await expect(commentInputs.nth(1)).toHaveAttribute('maxlength', '100')
    await commentInputs.nth(1).fill(comment)
    await staff.getByRole('button', { name: /^送/ }).click()
    await expect
      .poll(
        async () =>
          (await staffAlbum(staff.request, resident.id)).photos.filter((p) => !before.has(p.id))
            .length,
      )
      .toBe(2)
    const after = await staffAlbum(staff.request, resident.id)
    created.push(...after.photos.filter((p) => !before.has(p.id)).map((p) => p.id))
    const mine = after.photos.find((p) => p.comment === comment)
    if (!mine) throw new Error('コメント付きの写真が、一覧に見つかりません')
    // 載せたあと、すぐ下の「載せた写真」の一覧にも出る
    await expect(staff.locator('ul.grid li', { hasText: comment })).toBeVisible()

    // --- 5：家族 A が、下のメニューの「アルバム」（1 タップ。#396）で開く。コメントが見える ---
    await familyA.goto('/family')
    await familyA.getByRole('link', { name: /アルバム/ }).click()
    await expect(familyA.getByRole('heading', { name: 'アルバム' })).toBeVisible()
    await expect(familyA.getByText(comment)).toBeVisible()

    // --- 6：写真をタップすると、大きく出る。閉じられる ---
    await familyA.locator('li', { hasText: comment }).getByRole('button').click()
    const dialog = familyA.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText(comment)).toBeVisible()
    await dialog.getByRole('button', { name: /閉じる/ }).click()
    await expect(dialog).toBeHidden()

    // 黒い部分（写真・コメント・ボタンの外側）を押しても、閉じる
    await familyA.locator('li', { hasText: comment }).getByRole('button').click()
    await expect(dialog).toBeVisible()
    await dialog.click({ position: { x: 4, y: 4 } })
    await expect(dialog).toBeHidden()

    // --- 8：家族 B のアルバムには、A の写真が出ない ---
    await familyB.goto('/family/album')
    await expect(familyB.getByRole('heading', { name: 'アルバム' })).toBeVisible()
    await expect(familyB.getByText(comment)).toHaveCount(0)
    const bList = (await (await familyB.request.get('/api/family/album')).json()) as {
      days: { photos: Photo[] }[]
    }
    const bIds = bList.days.flatMap((day) => day.photos.map((p) => p.id))
    expect(bIds.some((id) => created.includes(id))).toBe(false)

    // --- 9：家族 B が、A の写真のファイルの URL を直接開くと 404 ---
    expect((await familyB.request.get(mine.url)).status()).toBe(404)

    // --- 10：ログインしていない人は 401 ---
    expect((await anonymous.request.get(mine.url)).status()).toBe(401)

    // --- 11：職員が、確認のうえ（2 回押して）削除する。一覧から消える ---
    await staff.reload()
    const row = staff.locator('ul.grid li', { hasText: comment })
    await row.getByRole('button', { name: /削除/ }).click()
    // 1 回目からすぐ（0.5 秒以内）の 2 回目は受け付けない
    await staff.waitForTimeout(800)
    await row.getByRole('button', { name: /もう.*押/ }).click()
    await expect(staff.getByRole('status').filter({ hasText: /削除.*しました/ })).toBeVisible()
    await expect(row).toHaveCount(0)

    // --- 12：家族 A がアルバムを開き直すと、削除した写真が出ない ---
    await familyA.goto('/family/album')
    await expect(familyA.getByRole('heading', { name: 'アルバム' })).toBeVisible()
    await expect(familyA.getByText(comment)).toHaveCount(0)

    // --- 13：削除した写真のファイルの URL は 404（ブラウザのキャッシュを使わない） ---
    expect((await familyA.request.get(mine.url)).status()).toBe(404)

    // --- 14：家族のロールで削除の API を呼ぶと 403 ---
    const other = created.find((id) => id !== mine.id)
    expect(other).toBeDefined()
    const denied = await familyA.request.delete(`/api/staff/album/${other}`, {
      headers: FETCH_HEADERS,
    })
    expect(denied.status()).toBe(403)
  } finally {
    // 載せた写真を、職員の API で削除する（削除済みを、もう一度削除しても 204）
    for (const id of created) {
      await staff.request.delete(`/api/staff/album/${id}`, { headers: FETCH_HEADERS })
    }
    await Promise.all([staff, familyA, familyB, anonymous].map((page) => page.context().close()))
  }
})
