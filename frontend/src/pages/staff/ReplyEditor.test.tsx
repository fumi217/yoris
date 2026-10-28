import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import type { StaffReply } from './recordValues'
import { ReplyEditor } from './ReplyEditor'

const reply: StaffReply = {
  id: 9,
  request_id: 5,
  theme_code: 'theme.meals',
  theme_emoji: '🍚',
  template_codes: ['template.meals.well'],
  note: '<b>よく</b>召し上がりました',
  replied_by_name: '職員B',
  replied_at: '2026-10-26T10:00:00+09:00',
  edited: false,
  read: false,
  template_ids: [21],
  template_options: [
    { id: 21, code: 'template.meals.well' },
    { id: 22, code: 'template.meals.less' },
  ],
  editable: true,
}

const render = (props: Partial<Parameters<typeof ReplyEditor>[0]> = {}) =>
  renderToStaticMarkup(
    <ReplyEditor
      reply={reply}
      saving={false}
      errorKey={null}
      onSave={() => {}}
      onClose={() => {}}
      {...props}
    />,
  )

describe('ReplyEditor', () => {
  it('選んでいた定型文と書き足しから始める', () => {
    const html = render()

    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1)
    expect(html.match(/aria-pressed="false"/g)).toHaveLength(1)
    // 書き足しは文字としてだけ入る
    expect(html).toContain('&lt;b&gt;よく&lt;/b&gt;召し上がりました')
  })

  it('直しても、家族にもう一度お知らせしないことを伝える', () => {
    expect(render()).toContain('お<ruby>知')
  })

  it('保存できなかったら、理由を出す', () => {
    expect(render({ errorKey: 'error.not_today' })).toContain('取り消したりできます')
  })
})
