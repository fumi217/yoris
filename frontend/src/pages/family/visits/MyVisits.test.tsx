import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../../../i18n'
import { FuriganaContext } from '../../../i18n/furigana'
import { MyVisitsView } from './MyVisits'
import type { MyReservation } from './visitDates'

const row = (overrides: Partial<MyReservation> = {}): MyReservation => ({
  id: 1,
  visit_date: '2026-10-28',
  start_time: '13:00:00',
  party_size: 2,
  status: 'booked',
  cancel_reason: null,
  can_cancel: true,
  ...overrides,
})

const render = (props: Partial<Parameters<typeof MyVisitsView>[0]> = {}) =>
  renderToStaticMarkup(
    <MyVisitsView
      rows={[row()]}
      cancellingId={null}
      notice={false}
      errorKey={null}
      onCancel={() => {}}
      {...props}
    />,
  )

describe('MyVisitsView', () => {
  it('これからの予約を、日時・人数・状態とともに出す', () => {
    const html = render()

    expect(html).toContain('13:00〜14:30')
    expect(html).toContain('28<ruby>日')
    expect(html).toContain('2<ruby>人')
    expect(html).toContain('予約済')
  })

  it('締め切りの前なら「取り消す」、過ぎたら電話の案内を出す', () => {
    expect(render()).toMatch(/<button[^>]*>.*取.*<\/button>/)

    const html = render({ rows: [row({ can_cancel: false })] })
    expect(html).not.toContain('<button')
    expect(html).toContain('お<ruby>電話')
    // 何の締め切りか分かるよう、時刻と「取り消し」の案内だと書く（#311）
    expect(html).toContain('17')
    expect(html).toMatch(/取.*り.*消.*すときは/)
  })

  it('施設が取り消した理由は、HTML として解釈しない', () => {
    const html = render({
      rows: [
        row({ status: 'cancelled_by_staff', cancel_reason: '<b>感染症</b>', can_cancel: false }),
      ],
    })

    expect(html).not.toContain('<b>感染症</b>')
    expect(html).toContain('&lt;b&gt;感染症&lt;/b&gt;')
    expect(html).toContain('<ruby>施設')
  })

  it('取り消した予約には、ボタンも電話の案内も出さない', () => {
    const html = render({ rows: [row({ status: 'cancelled_by_family', can_cancel: false })] })

    expect(html).not.toContain('<button')
    expect(html).not.toContain('お<ruby>電話')
  })

  it('予約がなければ、そう伝える', () => {
    expect(render({ rows: [] })).toContain('ありません')
  })

  it('取り消せなかったら、理由を出す（家族の画面なので、ふりがななし）', () => {
    const html = renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <MyVisitsView
          rows={[row()]}
          cancellingId={null}
          notice={false}
          errorKey="error.visit_deadline_passed"
          onCancel={() => {}}
        />
      </FuriganaContext.Provider>,
    )

    expect(html).toContain('施設にお電話ください')
  })
})

describe('家族の画面のふりがな（#260）', () => {
  it('家族の画面（FamilyRoutes の中）では、ふりがなを出さない', () => {
    const html = renderToStaticMarkup(
      <FuriganaContext.Provider value={false}>
        <MyVisitsView
          rows={[row()]}
          cancellingId={null}
          notice={false}
          errorKey={null}
          onCancel={() => {}}
        />
      </FuriganaContext.Provider>,
    )

    expect(html).not.toContain('<ruby>')
    expect(html).toContain('10月28日')
    expect(html).toContain('2人')
  })
})
