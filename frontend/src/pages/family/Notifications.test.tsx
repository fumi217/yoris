import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { NotificationsView } from './Notifications'
import {
  groupByDay,
  kindKey,
  linkFor,
  memoDateLink,
  noticeIconName,
  unreadCount,
  type FamilyNotification,
} from './notificationsView'

const notification = (overrides: Partial<FamilyNotification> = {}): FamilyNotification => ({
  id: 1,
  kind: 'reply',
  created_at: '2026-10-26T00:30:00Z',
  read: false,
  reply_id: 10,
  announcement_id: null,
  period_start: null,
  period_end: null,
  memo_dates: [],
  ...overrides,
})

// 今日は 2026-10-27（火）の昼（日本時間）にそろえる
const NOW = new Date('2026-10-27T03:00:00Z')

const render = (notifications: FamilyNotification[]) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <NotificationsView notifications={notifications} now={NOW} />
    </MemoryRouter>,
  )

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')

describe('NotificationsView', () => {
  it('まとめに入った様子のメモの書いた日から、その日の連絡帳へ進める（中身は出さない。FR-012b）', () => {
    const html = render([
      notification({
        kind: 'daily_digest',
        reply_id: null,
        memo_dates: ['2026-10-25', '2026-10-26'],
      }),
    ])

    expect(text(html)).toContain('様子のメモ')
    expect(text(html)).toContain('10月25日の連絡帳')
    expect(html).toContain('href="/family?date=2026-10-25"')
    expect(html).toContain('href="/family?date=2026-10-26"')
    // リンクの中にリンクを入れない
    expect(html).not.toMatch(/<a[^>]*>(?:(?!<\/a>).)*<a /)
  })

  it('メモが入らないお知らせには、メモの日付のリンクは出ない', () => {
    const html = render([notification({ kind: 'daily_digest', reply_id: null })])

    expect(html).not.toContain('date=')
    expect(memoDateLink('2026-10-25')).toBe('/family?date=2026-10-25')
  })

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
    // 日付は日ごとの見出しに、行には時刻だけ（日本時間）
    expect(shown).toContain('昨日（10月26日）')
    expect(shown).toContain('9:30')
  })

  it('面会のお知らせは、専用の文言で出る', () => {
    const shown = text(
      render([
        notification({ id: 1, kind: 'visit_confirmed', reply_id: null }),
        notification({ id: 2, kind: 'visit_cancelled', reply_id: null }),
        notification({ id: 3, kind: 'visit_reminder', reply_id: null }),
      ]),
    )

    expect(shown).toContain('面会の予約が確定しました')
    expect(shown).toContain('面会の予約が取り消されました')
    expect(shown).toContain('明日は面会の予定があります')
    expect(shown).not.toContain('施設からのお知らせ')
  })

  it('まだ読んでいないものにだけ「new」の印が出る', () => {
    const shown = text(render([notification({ id: 1 }), notification({ id: 2, read: true })]))

    expect(shown.match(/new/g)).toHaveLength(1)
  })

  it('面会のお知らせは、面会の画面へのリンクになる', () => {
    const html = render([
      notification({ id: 1, kind: 'visit_confirmed', reply_id: null }),
      notification({ id: 2, kind: 'visit_cancelled', reply_id: null }),
      notification({ id: 3, kind: 'visit_reminder', reply_id: null }),
    ])

    expect(html.match(/<a /g)).toHaveLength(3)
    expect(html.match(/href="\/family\/visits"/g)).toHaveLength(3)
  })

  it('お知らせがなければ、そう伝え、キャラクター（飾り）とやわらかい一言を出す（#350）', () => {
    const html = render([])

    expect(text(html)).toContain('お知らせはまだありません')
    expect(text(html)).toContain('また何かあればお知らせしますね。')
    expect(html).toMatch(/<img[^>]*alt=""/)
    // ホームと同じふわふわ（4.8 秒で止まる・動きを減らす設定では動かない）
    expect(html).toMatch(/<img[^>]*class="[^"]*mascot-float/)
  })

  it('お知らせが 1 つでもあれば、キャラクターは出さない', () => {
    const html = render([notification()])

    expect(html).not.toContain('<img')
    expect(text(html)).not.toContain('お知らせはまだありません')
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

    // 見出し・「new」の印・お知らせの文・日時、これだけ
    expect(shown).toBe('お知らせ未読 1 件昨日（10月26日）知りたいことへの返事が届きましたnew9:30')
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
    expect(kindKey('visit_confirmed')).toBe('notifications.kind.visit_confirmed')
    expect(kindKey('visit_cancelled')).toBe('notifications.kind.visit_cancelled')
    expect(kindKey('visit_reminder')).toBe('notifications.kind.visit_reminder')
    expect(kindKey('something_new')).toBe('notifications.kind.announcement')
  })

  it('進む先', () => {
    expect(linkFor(notification({ kind: 'reply' }))).toBe('/family')
    expect(linkFor(notification({ kind: 'weekly_digest' }))).toBe('/family')
    expect(linkFor(notification({ kind: 'staff_message_reply' }))).toBe('/family/inquiry')
    expect(linkFor(notification({ kind: 'visit_confirmed' }))).toBe('/family/visits')
    expect(linkFor(notification({ kind: 'visit_cancelled' }))).toBe('/family/visits')
    expect(linkFor(notification({ kind: 'visit_reminder' }))).toBe('/family/visits')
    expect(linkFor(notification({ kind: 'announcement' }))).toBeNull()
  })

  it('上に「未読 ◯ 件」を出す。0 件のときは出さない', () => {
    const some = text(
      render([
        notification({ id: 1 }),
        notification({ id: 2 }),
        notification({ id: 3, read: true }),
      ]),
    )
    const none = text(render([notification({ read: true })]))

    expect(some).toContain('未読 2 件')
    expect(none).not.toContain('未読')
  })

  it('未読は、薄い青の背景（unread）・太字・「new」の印の 3 つで示す。読んだものは、どれもない', () => {
    const unread = render([notification({ read: false })])
    const read = render([notification({ read: true })])

    expect(unread).toContain('bg-unread')
    expect(unread).toContain('font-bold')
    expect(text(unread)).toContain('new')
    expect(read).not.toContain('bg-unread')
    expect(read).not.toMatch(/<span class="block font-bold/)
    expect(text(read)).not.toContain('new')
  })

  it('日ごとの見出しでまとめる（今日・昨日・それ以外は日付と曜日）', () => {
    const shown = text(
      render([
        notification({ id: 1, created_at: '2026-10-27T01:00:00Z' }),
        notification({ id: 2, created_at: '2026-10-26T05:00:00Z' }),
        notification({ id: 3, created_at: '2026-10-23T05:00:00Z' }),
      ]),
    )

    expect(shown).toContain('今日（10月27日）')
    expect(shown).toContain('昨日（10月26日）')
    expect(shown).toContain('10月23日（金）')
    expect(shown.indexOf('今日（')).toBeLessThan(shown.indexOf('昨日（'))
    expect(shown.indexOf('昨日（')).toBeLessThan(shown.indexOf('10月23日'))
  })

  it('種類のアイコンを、行の左に出す（飾りなので読み上げない）', () => {
    const html = render([
      notification({ id: 1, kind: 'reply' }),
      notification({ id: 2, kind: 'announcement', reply_id: null }),
    ])

    expect(html).toContain('data-icon="comment-dots"')
    expect(html).toContain('data-icon="bullhorn"')
    expect(html.match(/<svg[^>]*aria-hidden="true"/g)?.length).toBeGreaterThanOrEqual(2)
  })

  it('押せる行にだけ、右に矢印を出す（進む先のない施設からのお知らせには出さない）', () => {
    const link = render([notification({ id: 1, kind: 'reply' })])
    const staticRow = render([notification({ id: 1, kind: 'announcement', reply_id: null })])

    expect(link).toContain('data-icon="chevron-right"')
    expect(staticRow).not.toContain('data-icon="chevron-right"')
  })

  it('1 つの白い面の中を、薄い線で区切る（行ごとのカードにしない）', () => {
    const html = render([notification({ id: 1 }), notification({ id: 2 })])

    expect(html.match(/<ul /g)).toHaveLength(1)
    expect(html).toContain('border-t border-card-line')
  })
})

describe('お知らせの見た目を決める部分', () => {
  it('種類ごとのアイコン。知らない種類は、施設からのお知らせと同じ', () => {
    expect(noticeIconName('reply')).toBe('notice-reply')
    expect(noticeIconName('daily_digest')).toBe('contact-book')
    expect(noticeIconName('weekly_digest')).toBe('contact-book')
    expect(noticeIconName('staff_message_reply')).toBe('inquiry')
    expect(noticeIconName('visit_confirmed')).toBe('notice-visit-confirmed')
    expect(noticeIconName('visit_cancelled')).toBe('notice-visit-cancelled')
    expect(noticeIconName('visit_reminder')).toBe('visits')
    expect(noticeIconName('announcement')).toBe('notice-announcement')
    expect(noticeIconName('something_new')).toBe('notice-announcement')
  })

  it('未読の数', () => {
    expect(unreadCount([])).toBe(0)
    expect(unreadCount([notification({ read: false }), notification({ id: 2, read: true })])).toBe(
      1,
    )
  })

  it('日ごとにまとめる：日本時間の日付で分け、順番は API のまま（日をまたぐ UTC に注意）', () => {
    const now = new Date('2026-10-27T03:00:00Z')
    const groups = groupByDay(
      [
        // UTC では 26 日の 15:30 だが、日本時間では 27 日の 0:30（今日）
        notification({ id: 1, created_at: '2026-10-26T15:30:00Z' }),
        notification({ id: 2, created_at: '2026-10-26T14:00:00Z' }),
        notification({ id: 3, created_at: '2026-10-20T00:00:00Z' }),
      ],
      now,
    )

    expect(groups.map((group) => [group.date, group.kind, group.items.length])).toEqual([
      ['2026-10-27', 'today', 1],
      ['2026-10-26', 'yesterday', 1],
      ['2026-10-20', 'other', 1],
    ])
    expect(groupByDay([], now)).toEqual([])
  })
})
