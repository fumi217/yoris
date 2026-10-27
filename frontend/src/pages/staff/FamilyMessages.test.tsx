import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { Ruby } from '../../i18n/Ruby'
import { adminMenuFor } from '../admin/adminMenu'
import { MessageDetailView } from './FamilyMessage'
import { MessageListView } from './FamilyMessages'
import {
  arrivedKey,
  canAssign,
  canReply,
  hasTemplates,
  listUrl,
  messagesBase,
  residentFilterOf,
  type ConversationMessage,
  type MessageDetail,
  type MessageRow,
} from './messagesView'

const row = (overrides: Partial<MessageRow> = {}): MessageRow => ({
  id: 1,
  resident_id: 10,
  resident_display_name: 'さくらさん',
  category: 'money',
  assignee: null,
  summary: '先月の請求書の金額について知りたい',
  status: 'waiting',
  handed_at: '2026-10-27T01:00:00Z',
  elapsed_days: 0,
  waiting_over_a_day: false,
  ...overrides,
})

const talk = (overrides: Partial<ConversationMessage> = {}): ConversationMessage => ({
  id: 1,
  sender: 'family',
  body: '先月の請求書の金額を教えてください',
  created_at: '2026-10-27T01:00:00Z',
  template_codes: null,
  note: null,
  ...overrides,
})

const detail = (overrides: Partial<MessageDetail> = {}): MessageDetail => ({
  ...row(),
  origin: talk(),
  previous: [],
  follow_ups: [],
  templates: [
    { id: 1, code: 'staff_template.money.check' },
    { id: 2, code: 'staff_template.money.next_invoice' },
  ],
  ...overrides,
})

/** 画面に出る文字だけにする（ふりがな・タグを除く）。 */
const text = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>/g, '')
    .replace(/<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/&gt;/g, '>')
    .replace(/&lt;/g, '<')
    .replace(/&amp;/g, '&')

const renderList = (messages: MessageRow[], status: 'waiting' | 'answered' = 'waiting') =>
  renderToStaticMarkup(
    <MemoryRouter>
      <MessageListView base="/staff/messages" status={status} messages={messages} />
    </MemoryRouter>,
  )

const renderDetail = (
  message: MessageDetail,
  errorKey: string | null = null,
  backTo = '/staff/messages',
) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <MessageDetailView
        backTo={backTo}
        message={message}
        assigning={false}
        sending={false}
        errorKey={errorKey}
        onAssign={vi.fn()}
        onReply={vi.fn()}
      />
    </MemoryRouter>,
  )

describe('MessageListView（一覧）', () => {
  it('入居者の呼び名・質問の種類・要約・担当（空なら「まだいません」）が出る（FR-012）', () => {
    const shown = text(
      renderList([row(), row({ id: 2, assignee: { id: 5, display_name: '西村' } })]),
    )

    expect(shown).toContain('さくらさん')
    expect(shown).toContain('お金・書類')
    expect(shown).toContain('先月の請求書の金額について知りたい')
    expect(shown).toContain('担当はまだいません')
    expect(shown).toContain('担当：西村')
  })

  it('API の並びのまま出し、詳細へのリンクは開いた側の URL の下（#88）', () => {
    const html = renderList([row({ id: 7 }), row({ id: 3 })])

    expect(html.indexOf('/staff/messages/7')).toBeLessThan(html.indexOf('/staff/messages/3'))
  })

  it('絞り込んだ一覧では、詳細へのリンクに絞り込みを引き継ぐ。詳細の「一覧へ」も絞り込みへ戻る（#88）', () => {
    const list = renderToStaticMarkup(
      <MemoryRouter>
        <MessageListView
          base="/staff/messages"
          status="waiting"
          messages={[row({ id: 7 })]}
          search="?resident_id=3"
        />
      </MemoryRouter>,
    )
    const detailHtml = renderDetail(detail(), null, '/staff/messages?resident_id=3')

    expect(list).toContain('href="/staff/messages/7?resident_id=3"')
    expect(detailHtml).toContain('href="/staff/messages?resident_id=3"')
  })

  it('メッセージがないときは、状態ごとの案内を出す', () => {
    expect(text(renderList([], 'waiting'))).toContain('対応待ちのメッセージはありません')
    expect(text(renderList([], 'answered'))).toContain('対応済みのメッセージはありません')
  })

  it('要約は文字のまま出る（HTML・ふりがなとして読まない。FR-028）', () => {
    const html = renderList([row({ summary: '<img src=x onerror=alert(1)> {漢字|かんじ}' })])

    expect(html).not.toContain('<img')
    expect(text(html)).toContain('{漢字|かんじ}')
  })

  it('受け付けてからの日数を出す（今日／◯日前）', () => {
    expect(text(renderList([row({ elapsed_days: 0 })]))).toContain('今日届きました')
    expect(text(renderList([row({ elapsed_days: 2 })]))).toContain('2日前に届きました')
    expect(arrivedKey(0)).toBe('family_messages.arrived_today')
    expect(arrivedKey(3)).toBe('family_messages.arrived_days')
  })
})

describe('MessageDetailView（詳細）', () => {
  it('原文・要約・種類・担当・直前のやりとり・追加の書き込みが出る（FR-011・FR-012）', () => {
    const shown = text(
      renderDetail(
        detail({
          previous: [talk({ id: 0, body: '前の質問' })],
          follow_ups: [talk({ id: 9, body: '追加の書き込み' })],
        }),
      ),
    )

    expect(shown).toContain('先月の請求書の金額を教えてください')
    expect(shown).toContain('先月の請求書の金額について知りたい')
    expect(shown).toContain('お金・書類')
    expect(shown).toContain('直前のやりとり')
    expect(shown).toContain('前の質問')
    expect(shown).toContain('追加の書き込み')
  })

  it('担当がいない対応待ちには「自分が対応する」が出て、担当がいれば出ない（FR-012b）', () => {
    expect(text(renderDetail(detail()))).toContain('自分が対応する')

    const assigned = detail({ assignee: { id: 5, display_name: '西村' } })
    expect(text(renderDetail(assigned))).not.toContain('自分が対応する')
    expect(canAssign(assigned)).toBe(false)
  })

  it('定型文のボタンと、100 文字までの書き足しの欄が出る（FR-014）', () => {
    const shown = text(renderDetail(detail()))

    expect(shown).toContain('確認して、改めてお知らせします')
    expect(shown).toContain('次の請求書でお知らせします')
    expect(shown).toContain('0 / 100')
    // 何も選んでいないときは送れない（定型文は 1 つ以上）
    expect(renderDetail(detail())).toMatch(/<button type="submit" disabled=""/)
  })

  it('苦情には定型文がなく、電話で対応する案内を出す（FR-014）', () => {
    const complaint = detail({ category: 'complaint', templates: [] })

    expect(hasTemplates(complaint.templates)).toBe(false)
    const shown = text(renderDetail(complaint))
    expect(shown).toContain('定型文がありません')
    expect(shown).not.toContain('定型文を選んでください')
  })

  it('対応済みには返事の欄を出さない（FR-017）', () => {
    const answered = detail({ status: 'answered' })

    expect(canReply(answered)).toBe(false)
    const shown = text(renderDetail(answered))
    expect(shown).toContain('返事をしました')
    expect(shown).not.toContain('定型文を選んでください')
  })

  it('職員の返事は定型文と書き足しで出る。文はそのまま文字として出る（FR-028）', () => {
    const shown = text(
      renderDetail(
        detail({
          previous: [
            talk({
              id: 2,
              sender: 'staff',
              body: '',
              template_codes: ['staff_template.money.check'],
              note: '<b>来週</b>お知らせします',
            }),
          ],
        }),
      ),
    )

    expect(shown).toContain('施設の職員')
    expect(shown).toContain('確認して、改めてお知らせします')
    expect(shown).toContain('<b>来週</b>お知らせします')
  })

  it('API のエラーのときは、渡された辞書のキーの文言を、警告（role="alert"）として出す', () => {
    // 409 の文言（error.already_assigned・error.already_answered）の辞書は #233 で入った。
    // ここでは、画面が errorKey をそのまま出すことだけを確かめる
    const html = renderDetail(detail(), 'error.already_assigned')

    expect(html).toContain('role="alert"')
    expect(text(html)).toContain('ほかの職員が対応しています')
  })
})

describe('messagesBase', () => {
  it('職員の画面から開いたときと、管理画面から開いたときで、URL の頭が変わる（事務員は管理画面から）', () => {
    expect(messagesBase('/staff/messages')).toBe('/staff/messages')
    expect(messagesBase('/staff/messages/3')).toBe('/staff/messages')
    expect(messagesBase('/admin/messages')).toBe('/admin/messages')
    expect(messagesBase('/admin/messages/3')).toBe('/admin/messages')
  })
})

describe('管理画面のトップの入り口', () => {
  it('生活相談員・施設長・事務員に「家族からのメッセージ」が出て、ほかの役割には出ない', () => {
    const has = (role: Parameters<typeof adminMenuFor>[0]) =>
      adminMenuFor(role).some((item) => item.to === '/admin/messages')

    expect(has('clerk')).toBe(true)
    expect(has('counselor')).toBe(true)
    expect(has('director')).toBe(true)
    expect(has('care_worker')).toBe(false)
    expect(has('leader')).toBe(false)
  })

  it('入り口には、対応待ちの件数を添える', () => {
    const item = adminMenuFor('clerk').find((entry) => entry.to === '/admin/messages')

    expect(item?.showMessageCount).toBe(true)
  })
})

describe('管理画面のトップの件数', () => {
  it('件数の読み上げに、何の数かを添える（「3」だけにならない）', () => {
    expect(
      text(renderToStaticMarkup(<Ruby text={i18n.t('admin.waiting_messages', { count: 3 })} />)),
    ).toBe('対応待ち 3 件')
  })
})

describe('入居者での絞り込み（?resident_id=。#88）', () => {
  it('正の整数が 1 つだけのときに、絞り込む入居者の id として読む', () => {
    expect(residentFilterOf('?resident_id=12')).toBe(12)
    expect(residentFilterOf('resident_id=3&other=x')).toBe(3)
    // 安全な整数の範囲のいちばん大きい数までは読める
    expect(residentFilterOf('?resident_id=9007199254740991')).toBe(9007199254740991)
  })

  it('ないとき・正の整数でないとき・複数あるときは、絞り込まない', () => {
    for (const search of [
      '',
      '?',
      '?resident_id=',
      '?resident_id=0',
      '?resident_id=-1',
      '?resident_id=abc',
      '?resident_id=1.5',
      '?resident_id=1e3',
      '?resident_id=12abc',
      '?resident_id=1&resident_id=2',
      // 安全な整数の範囲（9007199254740991）を超えるもの。Number() で丸められて別の値になる
      '?resident_id=9007199254740992',
      '?resident_id=9999999999999999',
      `?resident_id=${'9'.repeat(30)}`,
    ]) {
      expect(residentFilterOf(search)).toBeNull()
    }
  })

  it('一覧の API の URL に、状態と、読めた入居者の id だけを渡す', () => {
    expect(listUrl('waiting', null)).toBe('/api/staff/messages?status=waiting')
    expect(listUrl('answered', 7)).toBe('/api/staff/messages?status=answered&resident_id=7')
  })

  it('絞り込みの案内の文言が、ふりがなを外して読める', () => {
    expect(text(renderToStaticMarkup(<Ruby text={i18n.t('family_messages.filtered')} />))).toBe(
      'この入居者のメッセージだけを表示しています',
    )
    expect(text(renderToStaticMarkup(<Ruby text={i18n.t('family_messages.show_all')} />))).toBe(
      'すべての入居者を見る',
    )
  })
})
