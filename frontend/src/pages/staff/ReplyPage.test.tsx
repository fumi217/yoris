import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { noteLength, replyBody, toggleTemplate, type WaitingRequest } from './replyForm'
import { ReplyView } from './ReplyPage'

const request = (overrides: Partial<WaitingRequest> = {}): WaitingRequest => ({
  id: 5,
  theme_code: 'theme.meals',
  theme_emoji: '🍚',
  created_at: '2026-10-24T01:00:00Z', // 日本時間の 10/24 10:00
  days: 2,
  templates: [
    { id: 11, code: 'template.meals.well' },
    { id: 12, code: 'template.meals.less' },
  ],
  ...overrides,
})

const render = (props: Partial<Parameters<typeof ReplyView>[0]> = {}) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ReplyView
        residentId="3"
        resident={{ id: 3, display_name: '佐藤さんの母', room: '101' }}
        requests={[request()]}
        sendingId={null}
        errorKey={null}
        onSend={() => {}}
        {...props}
      />
    </MemoryRouter>,
  )

describe('replyForm', () => {
  it('定型文は、選んだ順に並べ、もう一度押すと外す', () => {
    expect(toggleTemplate([12], 11)).toEqual([12, 11])
    expect(toggleTemplate([12, 11], 12)).toEqual([11])
  })

  it('書き足しは、絵文字も 1 文字と数える', () => {
    expect(noteLength('笑顔😊')).toBe(3)
  })

  it('空白だけの書き足しは送らない', () => {
    expect(replyBody([11], '   ')).toEqual({ template_ids: [11], note: null })
    expect(replyBody([11], ' よく召し上がりました ')).toEqual({
      template_ids: [11],
      note: 'よく召し上がりました',
    })
  })
})

describe('ReplyView', () => {
  it('テーマ・送られた日時・日数と、そのテーマの定型文のボタンを出す', () => {
    const html = render()

    expect(html).toContain('🍚')
    expect(html).toContain('10:00')
    expect(html).toContain('24<ruby>日')
    expect(html).toContain('2<ruby>日')
    expect(html.match(/aria-pressed="false"/g)).toHaveLength(2)
  })

  it('定型文を選ぶまでは、送れない', () => {
    expect(render()).toMatch(/<button type="submit" disabled=""/)
  })

  it('返事待ちがなければ、そう伝える', () => {
    expect(render({ requests: [] })).toContain('リクエストはありません')
  })

  it('ほかの職員が先に返事をしたら、そう伝える', () => {
    expect(render({ errorKey: 'error.already_replied' })).toContain('をしました')
  })

  it('記録の画面に戻るリンクがある', () => {
    expect(render()).toContain('href="/staff/residents/3"')
  })
})
