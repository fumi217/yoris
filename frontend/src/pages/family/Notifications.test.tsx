import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { NotificationsView } from './Notifications'
import { kindKey, linkFor, type FamilyNotification } from './notificationsView'

const notification = (overrides: Partial<FamilyNotification> = {}): FamilyNotification => ({
  id: 1,
  kind: 'reply',
  created_at: '2026-10-26T00:30:00Z',
  read: false,
  reply_id: 10,
  announcement_id: null,
  period_start: null,
  period_end: null,
  ...overrides,
})

const render = (notifications: FamilyNotification[]) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <NotificationsView notifications={notifications} />
    </MemoryRouter>,
  )

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('NotificationsView', () => {
  it('種類ごとの文言と、日本時間の日時が出る', () => {
    const shown = text(
      render([
        notification({ id: 1, kind: 'reply' }),
        notification({ id: 2, kind: 'daily_digest', reply_id: null }),
        notification({ id: 3, kind: 'weekly_digest', reply_id: null }),
        notification({ id: 4, kind: 'announcement', reply_id: null, announcement_id: 7 }),
        notification({ id: 5, kind: 'staff_message_reply', reply_id: null }),
      ]),
    )

    expect(shown).toContain('知りたいことへの返事が届きました')
    expect(shown).toContain('今日の連絡帳がまとまりました')
    expect(shown).toContain('今週の連絡帳がまとまりました')
    expect(shown).toContain('施設からのお知らせが届きました')
    expect(shown).toContain('施設からメッセージの返事が届きました')
    expect(shown).toContain('10月26日 9:30')
  })

  it('まだ読んでいないものにだけ「新しい」の印が出る', () => {
    const shown = text(render([notification({ id: 1 }), notification({ id: 2, read: true })]))

    expect(shown.match(/新しい/g)).toHaveLength(1)
  })

  it('お知らせがなければ、そう伝える', () => {
    expect(text(render([]))).toContain('お知らせはまだありません')
  })

  it('返事・まとめは連絡帳へのリンク、施設からのお知らせはリンクにしない', () => {
    const html = render([
      notification({ id: 1, kind: 'reply' }),
      notification({ id: 2, kind: 'announcement', reply_id: null }),
    ])

    expect(html.match(/<a /g)).toHaveLength(1)
    expect(html).toContain('href="/family"')
  })

  it('職員の返事のお知らせは、「お問い合わせ」の画面へのリンクになる', () => {
    const html = render([notification({ id: 1, kind: 'staff_message_reply', reply_id: null })])

    expect(html.match(/<a /g)).toHaveLength(1)
    expect(html).toContain('href="/family/inquiry"')
  })

  it('返事のお知らせは、種類と日時の文だけで、ほかの文字は出ない（SC-010）', () => {
    const shown = text(render([notification()]))

    // 見出し・「新しい」の印・お知らせの文・日時、これだけ
    expect(shown).toBe('お知らせ新しい知りたいことへの返事が届きました10月26日 9:30')
  })

  it('API がうっかり返事の中身や職員の名前を返しても、画面には出ない', () => {
    // 今の API は返さないが、将来返すようになっても、一覧には出さない
    const leaked = {
      ...notification(),
      note: 'ひみつの書き足し',
      replied_by_name: 'ひみつの職員',
      template_codes: ['template.daily_life.usual'],
    } as unknown as FamilyNotification

    const html = render([leaked])

    expect(html).not.toContain('ひみつの書き足し')
    expect(html).not.toContain('ひみつの職員')
    expect(html).not.toContain('いつもどおり')
  })
})

describe('notificationsView', () => {
  it('知らない種類は、施設からのお知らせの文言にする', () => {
    expect(kindKey('reply')).toBe('notifications.kind.reply')
    expect(kindKey('staff_message_reply')).toBe('notifications.kind.staff_message_reply')
    expect(kindKey('something_new')).toBe('notifications.kind.announcement')
  })

  it('進む先', () => {
    expect(linkFor(notification({ kind: 'reply' }))).toBe('/family')
    expect(linkFor(notification({ kind: 'weekly_digest' }))).toBe('/family')
    expect(linkFor(notification({ kind: 'staff_message_reply' }))).toBe('/family/inquiry')
    expect(linkFor(notification({ kind: 'announcement' }))).toBeNull()
  })
})
