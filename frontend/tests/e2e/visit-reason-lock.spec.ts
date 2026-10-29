import { expect, test, type Page } from '@playwright/test'
import { loginAs } from './helpers'

// #317：2 回押して決めるボタン（ConfirmButton）が確かめの状態のあいだ、取り消し・休みの「理由」の欄を
// 読み取り専用にして、「やめる」で戻すと直せる。確かめた内容と送る内容がずれないようにするため。
// 確かめる画面は 2 つ：職員の面会の予約の一覧（予約の取り消し）と、面会の設定（予約の入った日を休みにする）。
//
// 開発の DB を使う。確かめるだけで、2 回目は押さないので、予約は取り消さず、日は休みにしない。
// 画面を出すために、家族 A が 1 件予約し、最後に家族 A が自分で取り消す（家族の取り消しはお知らせを作らない）。
// 予約したときの「予約が確定しました」のお知らせとメール（Mailpit）は残る。

const FETCH_HEADERS = { 'X-Requested-With': 'fetch' }

type Day = {
  date: string
  closed: boolean
  mine: boolean
  start_times: { start_time: string; selectable: boolean }[]
}

/** 日本時間の今日から days 日あと（"YYYY-MM-DD"）。 */
function daysFromToday(days: number): string {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo' }).format(new Date())
  const value = new Date(`${today}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

// 職員・管理の画面は、すべての漢字にふりがな（<ruby>）が付く。ボタンの名前には読みも入るので、
// 漢字の間にほかの文字が入ってもよい書き方で探す
const OPEN_CANCEL = /^取.*り.*消.*す$/
const SUBMIT_CANCEL = /^予.*約.*を.*取.*り.*消.*す$/
const CLOSE_THE_DAY = /^休.*み.*に.*す.*る$/
const CLOSE_AND_CANCEL = /^予.*約.*を.*取.*り.*消.*し.*て.*休.*み.*に.*す.*る$/

// 案内の文（ふりがなの間に読みが入るので、漢字を含まない部分だけで探す）
const HINT_BEFORE = 'いてから、ボタンを'
const HINT_LOCKED = 'すときは「やめる」を'

/**
 * 理由の欄が、確かめの状態に入ると読み取り専用になり（disabled ではない）、案内の文が変わり、
 * 「やめる」で戻すと直せるようになる。確かめるボタンは 1 回しか押さない。
 */
async function checkReasonLocksWhileConfirming(page: Page, submit: RegExp) {
  // 日付の入力欄も textbox に数えられるので、理由の欄（textarea）で探す
  const reason = page.locator('textarea')
  await expect(reason).toBeEditable()
  await expect(page.getByText(HINT_BEFORE)).toBeVisible()
  await expect(page.getByText(HINT_LOCKED)).toHaveCount(0)
  await reason.fill('工事のため')

  // 1 回目：確かめの状態に入る
  await page.getByRole('button', { name: submit }).click()
  await expect(reason).not.toBeEditable()
  await expect(reason).not.toBeDisabled()
  await expect(reason).toHaveAttribute('readonly', '')
  await expect(page.getByText(HINT_LOCKED)).toBeVisible()
  await expect(page.getByText(HINT_BEFORE)).toHaveCount(0)
  // 打ち込もうとしても、理由は変わらない
  await reason.press('x')
  await expect(reason).toHaveValue('工事のため')

  // 「やめる」で戻す：もう一度直せる
  await page.getByRole('button', { name: 'やめる', exact: true }).click()
  await expect(reason).toBeEditable()
  await expect(page.getByText(HINT_BEFORE)).toBeVisible()
  await reason.fill('日程が変わったため')
  await expect(reason).toHaveValue('日程が変わったため')
}

test('取り消し・休みの理由の欄は、2 回押す確かめの状態のあいだだけ読み取り専用になる（#317）', async ({
  page,
}) => {
  // 家族 A が 1 件予約する（職員の予約の一覧と、「予約の入った日」を用意するため）
  await loginAs(page, { kind: 'family', index: 0 })
  const availability = (await (
    await page.request.get(
      `/api/family/visits/availability?from=${daysFromToday(2)}&to=${daysFromToday(28)}`,
    )
  ).json()) as { days: Day[] }
  const target = availability.days.find(
    (day) => !day.closed && !day.mine && day.start_times.some((slot) => slot.selectable),
  )
  if (!target)
    throw new Error('空いている日がありません（開発の DB の予約・休みの日を確かめてください）')
  const date = target.date
  const startTime = target.start_times.find((slot) => slot.selectable)!.start_time

  const booked = await page.request.post('/api/family/visits', {
    data: { visit_date: date, start_time: startTime, party_size: 1 },
    headers: FETCH_HEADERS,
  })
  expect(booked.status()).toBe(201)

  try {
    await test.step('職員の面会の予約の一覧：「取り消す」を開いて、理由の欄を確かめる', async () => {
      await loginAs(page, { kind: 'staff', role: 'leader' })
      await page.goto('/staff/visits')
      // 先頭の予約の「取り消す」を開く（家族 A の予約とは限らない。2 回目は押さないので、
      // どの予約でも、取り消しは起きない）
      await page.getByRole('button', { name: OPEN_CANCEL }).first().click()

      await checkReasonLocksWhileConfirming(page, SUBMIT_CANCEL)
    })

    await test.step('面会の設定：予約の入った日を「休みにする」と、理由の欄を確かめる', async () => {
      await loginAs(page, { kind: 'staff', role: 'counselor' })
      await page.goto('/admin/visit-settings')
      await page.locator('input[type="date"]').fill(date)
      // その日には家族 A の予約があるので、日は休みにならず、件数と理由の入力が出る（409）
      await page.getByRole('button', { name: CLOSE_THE_DAY, exact: false }).first().click()
      await expect(page.getByRole('alert')).toBeVisible()

      await checkReasonLocksWhileConfirming(page, CLOSE_AND_CANCEL)
    })
  } finally {
    // 片付け：休みにしてしまっていたら戻し、家族 A が自分の予約を取り消す
    await loginAs(page, { kind: 'staff', role: 'counselor' })
    const closed = (await (
      await page.request.get(`/api/admin/visit-closed-days?from=${date}&to=${date}`)
    ).json()) as { id: number }[]
    for (const day of closed) {
      await page.request.delete(`/api/admin/visit-closed-days/${day.id}`, {
        headers: FETCH_HEADERS,
      })
    }
    await loginAs(page, { kind: 'family', index: 0 })
    const mine = (await (await page.request.get('/api/family/visits')).json()) as {
      id: number
      visit_date: string
      status: string
    }[]
    for (const row of mine.filter((r) => r.visit_date === date && r.status === 'booked')) {
      const cancelled = await page.request.delete(`/api/family/visits/${row.id}`, {
        headers: FETCH_HEADERS,
      })
      if (!cancelled.ok())
        console.warn(`片付け：予約 ${row.id} を取り消せませんでした（${cancelled.status()}）`)
    }
  }
})
