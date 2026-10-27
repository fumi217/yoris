import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { InquiryView } from './Inquiry'
import {
  aiNoticeKey,
  showsCallIfUrgent,
  chronological,
  marksNoticeRead,
  nextBefore,
  PAGE_SIZE,
  sourceParts,
  type InquiryMessage,
} from './inquiryView'

// 家族の「お問い合わせ」（AI に質問する）画面のテスト（spec 004 の 004-T021。FR-005・FR-012a・FR-028）

const message = (overrides: Partial<InquiryMessage> = {}): InquiryMessage => ({
  id: 1,
  sender: 'family',
  body: '今日のお昼は食べましたか？',
  created_at: '2026-10-26T03:00:00Z',
  ai_result: null,
  sources: [],
  hidden: false,
  staff_name: null,
  template_codes: null,
  note: null,
  response_type: null,
  ...overrides,
})

const answer = (overrides: Partial<InquiryMessage> = {}) =>
  message({
    id: 2,
    sender: 'ai',
    body: '今日のお昼は、ほぼ全部召し上がりました。',
    ai_result: 'answered',
    sources: [
      { kind: 'record', date: '2026-10-23', item: 'meal', slot: 'lunch', theme_code: null },
    ],
    ...overrides,
  })

const render = (props: Partial<Parameters<typeof InquiryView>[0]> = {}) =>
  renderToStaticMarkup(
    <InquiryView
      messages={[]}
      hasOlder={false}
      onLoadOlder={() => {}}
      draft=""
      onDraftChange={() => {}}
      sending={null}
      errorKey={null}
      onSend={() => {}}
      {...props}
    />,
  )

// 画面に見える文字だけ（ふりがなの <rt>・<rp> とタグを外す）
const visibleText = (html: string) =>
  html
    .replace(/<rt>.*?<\/rt>|<rp>.*?<\/rp>/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/&quot;/g, '"')

describe('InquiryView', () => {
  it('見出しはメニューと同じ「お問い合わせ」。職員に伝えることを、会話がなくても出す（FR-012a）', () => {
    const text = visibleText(render())

    expect(text).toContain('お問い合わせ')
    expect(text).toContain('AI がお答えできないときは、施設の職員にこの会話の一部をお伝えします')
    expect(text).toContain('まだ質問はありません')
  })

  it('AI の答えのそばに「AI がお答えしています」ともとにした記録を出す（FR-004・FR-005）', () => {
    const text = visibleText(render({ messages: [message(), answer()] }))

    expect(text).toContain('今日のお昼は、ほぼ全部召し上がりました。')
    expect(text).toContain('AI がお答えしています。記録にないことはお答えできません')
    expect(text).toContain('もとにした記録')
    expect(text).toContain('10月23日・食事・昼')
  })

  it('職員に渡したときは決まった文を出し、緊急のときだけ電話の案内も出す（FR-009）', () => {
    const handedOff = (handoff: InquiryMessage['handoff']) =>
      visibleText(
        render({
          messages: [answer({ body: '', ai_result: 'handed_off', sources: [], handoff })],
        }),
      )

    const normal = handedOff({ status: 'waiting', urgent: false, already: false })
    expect(normal).toContain('この内容は施設の職員からお答えします。施設の職員にお伝えしました')
    // 緊急でないときは、電話の案内を出さない（spec 004 の Edge Cases）
    expect(normal).not.toContain('お急ぎのときは、施設にお電話ください')

    const urgent = handedOff({ status: 'waiting', urgent: true, already: false })
    expect(urgent).toContain('施設の職員にお伝えしました')
    expect(urgent).toContain('お急ぎのときは、施設にお電話ください')
  })

  it('同じ内容の対応待ちにつないだときは「すでに施設の職員にお伝えしています」（FR-016）', () => {
    const text = visibleText(
      render({
        messages: [
          answer({
            body: '',
            ai_result: 'handed_off',
            sources: [],
            handoff: { status: 'waiting', urgent: false, already: true },
          }),
        ],
      }),
    )

    expect(text).toContain('すでに施設の職員にお伝えしています')
    expect(text).not.toContain('この内容は施設の職員からお答えします')
  })

  it('handoff が来ない古い API のときも動く（「お伝えしました」だけ。電話の案内は出さない）', () => {
    const text = visibleText(
      render({ messages: [answer({ body: '', ai_result: 'handed_off', sources: [] })] }),
    )

    expect(text).toContain('施設の職員にお伝えしました')
    expect(text).not.toContain('お急ぎのときは、施設にお電話ください')
  })

  it('根拠が非開示になった答えは「いまはお見せできません」（FR-008）', () => {
    const text = visibleText(
      render({ messages: [answer({ body: '', sources: [], hidden: true })] }),
    )

    expect(text).toContain('この答えは、いまはお見せできません')
    expect(text).not.toContain('もとにした記録')
  })

  it('職員の返事は「◯◯からの返事」と、AI の答えと区別して出す（FR-005）', () => {
    const staff = message({
      id: 3,
      sender: 'staff',
      body: '',
      staff_name: '山本',
      template_codes: ['staff_template.care_request.next_visit'],
      note: '冬の上着をお預かりします',
      response_type: 'app',
    })

    const text = visibleText(render({ messages: [staff] }))

    expect(text).toContain('山本からの返事')
    expect(text).toContain('次の面会のときにお渡しします')
    expect(text).toContain('冬の上着をお預かりします')
    expect(text).not.toContain('AI がお答えしています')
  })

  it('職員の名前は、ふりがなの書き方と取り違えず、そのまま出す', () => {
    const staff = message({
      id: 3,
      sender: 'staff',
      body: '',
      staff_name: '{山|やま}本',
      note: null,
    })

    const html = render({ messages: [staff] })

    expect(visibleText(html)).toContain('{山|やま}本からの返事')
    expect(html).not.toContain('<rt>やま</rt>')
  })

  it('家族の文・AI の答えは文字としてだけ出す（タグは実行されない。FR-028）', () => {
    const html = render({
      messages: [
        message({ body: '<script>alert(1)</script>' }),
        answer({ body: '<img src=x onerror=alert(1)>' }),
      ],
    })

    expect(html).not.toContain('<script>')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
  })

  it('送っている間は、質問と「AI が記録を調べています…」を出し、送るボタンを押せない', () => {
    const html = render({ draft: 'お昼は？', sending: 'お昼は？' })

    expect(visibleText(html)).toContain('お昼は？')
    expect(visibleText(html)).toContain('AI が記録を調べています…')
    expect(html).toMatch(/<button type="submit" disabled=""/)
  })

  it('空の質問・500 文字を超える質問は送れない（FR-001）', () => {
    expect(render({ draft: '   ' })).toMatch(/<button type="submit" disabled=""/)

    const tooLong = render({ draft: 'あ'.repeat(501) })
    expect(tooLong).toMatch(/<button type="submit" disabled=""/)
    expect(visibleText(tooLong)).toContain('500 文字までで書いてください')

    expect(render({ draft: 'あ'.repeat(500) })).not.toMatch(/<button type="submit" disabled=""/)
    // 絵文字も 1 文字と数える（backend とそろえる）
    expect(render({ draft: '😀'.repeat(500) })).not.toMatch(/<button type="submit" disabled=""/)
    expect(render({ draft: '😀'.repeat(501) })).toMatch(/<button type="submit" disabled=""/)
  })

  it('AI につながらなかったときの案内を出す（FR-026）', () => {
    const text = visibleText(render({ draft: 'お昼は？', errorKey: 'error.ai_unavailable' }))

    expect(text).toContain('いまお答えできません')
  })

  it('1 日の回数に達したときは、明日また使えることと電話の案内を出し、書いた文は残す（FR-024）', () => {
    const html = render({ draft: 'お昼は？', errorKey: 'error.inquiry_limit' })

    expect(visibleText(html)).toContain('今日の質問は上限に達しました。明日またご利用ください')
    expect(visibleText(html)).toContain('お急ぎのときは、施設にお電話ください')
    expect(html).toContain('お昼は？')
  })
})

describe('inquiryView', () => {
  it('既読を送るのは、アプリで返した職員の返事だけ（Issue #244）', () => {
    expect(marksNoticeRead(message({ sender: 'staff', response_type: 'app' }))).toBe(true)
    // 電話で対応した発言は、お知らせがないので送らない
    expect(marksNoticeRead(message({ sender: 'staff', response_type: 'phone' }))).toBe(false)
    expect(marksNoticeRead(message({ sender: 'ai', response_type: null }))).toBe(false)
    expect(marksNoticeRead(message({ sender: 'family', response_type: null }))).toBe(false)
  })

  it('新しい順に届いた発言を、古い順に並べ直す（FR-008）', () => {
    const pages = [[message({ id: 5 }), message({ id: 4 })], [message({ id: 2 })]]

    expect(chronological(pages).map((m) => m.id)).toEqual([2, 4, 5])
  })

  it('続きは、読んだ中でいちばん古い id より前を読む。読み切ったら終わり', () => {
    const full = Array.from({ length: PAGE_SIZE }, (_, i) => message({ id: 100 - i }))

    expect(nextBefore(full)).toBe(100 - PAGE_SIZE + 1)
    expect(nextBefore([message({ id: 3 })])).toBeUndefined()
  })

  it('AI の発言で、本文の代わりに出す文を決める', () => {
    expect(aiNoticeKey(answer())).toBeNull()
    expect(aiNoticeKey(answer({ ai_result: 'no_record' }))).toBe('inquiry.no_record')
    expect(aiNoticeKey(answer({ ai_result: 'handed_off' }))).toBe('inquiry.handed_off')
    expect(aiNoticeKey(answer({ hidden: true }))).toBe('inquiry.answer_hidden')
  })

  it('職員に渡した発言の文と電話の案内は、handoff で決まる（FR-016・Edge Cases）', () => {
    const handedOff = (handoff: InquiryMessage['handoff']) =>
      answer({ ai_result: 'handed_off', handoff })

    expect(aiNoticeKey(handedOff({ status: 'waiting', urgent: false, already: true }))).toBe(
      'inquiry.already_handed_off',
    )
    expect(aiNoticeKey(handedOff({ status: 'waiting', urgent: false, already: false }))).toBe(
      'inquiry.handed_off',
    )
    // 電話の案内は、緊急のときだけ。根拠が非開示になった答え・handoff がないときは出さない
    expect(showsCallIfUrgent(handedOff({ status: 'waiting', urgent: true, already: false }))).toBe(
      true,
    )
    expect(showsCallIfUrgent(handedOff({ status: 'waiting', urgent: false, already: false }))).toBe(
      false,
    )
    expect(showsCallIfUrgent(handedOff(undefined))).toBe(false)
    expect(
      showsCallIfUrgent({
        ...handedOff({ status: 'waiting', urgent: true, already: false }),
        hidden: true,
      }),
    ).toBe(false)
    expect(showsCallIfUrgent(answer())).toBe(false)
  })

  it('もとにした記録・返事を、日付と辞書のキーにする（機嫌・眠りの区分は出さない）', () => {
    expect(
      sourceParts({
        kind: 'record',
        date: '2026-10-23',
        item: 'mood',
        slot: 'day',
        theme_code: null,
      }),
    ).toEqual({ month: 10, day: 23, labelKeys: ['record.item.mood'] })
    expect(
      sourceParts({
        kind: 'reply',
        date: '2026-10-01',
        item: null,
        slot: null,
        theme_code: 'theme.meals',
      }),
    ).toEqual({ month: 10, day: 1, labelKeys: ['theme.meals'] })
  })
})
