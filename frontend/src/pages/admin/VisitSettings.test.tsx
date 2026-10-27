import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/client'
import '../../i18n'
import { adminMenuFor } from './adminMenu'
import { ClosedDaysView, SettingsFormView } from './VisitSettings'
import {
  CANDIDATE_TIMES,
  clampDailyLimit,
  closedDaysRange,
  reasonProblem,
  reservationCountOf,
  toggleTime,
} from './visitSettingsRules'

const renderForm = (props: Partial<Parameters<typeof SettingsFormView>[0]> = {}) =>
  renderToStaticMarkup(
    <SettingsFormView
      initial={{ daily_limit: 2, start_times: ['10:00:00', '13:00:00'] }}
      saving={false}
      saved={false}
      errorKey={null}
      onSave={() => {}}
      {...props}
    />,
  )

const renderDays = (props: Partial<Parameters<typeof ClosedDaysView>[0]> = {}) =>
  renderToStaticMarkup(
    <ClosedDaysView
      today="2026-10-27"
      days={[]}
      loadErrorKey={null}
      pending={null}
      busy={false}
      notice={null}
      errorKey={null}
      onClose={() => {}}
      onConfirmClose={() => {}}
      onDismiss={() => {}}
      onOpen={() => {}}
      {...props}
    />,
  )

describe('visitSettingsRules', () => {
  it('選べる時刻は、10:00 から 15:30 までの 30 分刻み（17:00 までに終わる）', () => {
    expect(CANDIDATE_TIMES[0]).toBe('10:00:00')
    expect(CANDIDATE_TIMES.at(-1)).toBe('15:30:00')
    expect(CANDIDATE_TIMES).toHaveLength(12)
  })

  it('時刻を選ぶ・外すと、いつも早い順になる', () => {
    expect(toggleTime(['13:00:00'], '10:30:00')).toEqual(['10:30:00', '13:00:00'])
    expect(toggleTime(['10:30:00', '13:00:00'], '10:30:00')).toEqual(['13:00:00'])
  })

  it('組数は 1 より少なくできない', () => {
    expect(clampDailyLimit(0)).toBe(1)
    expect(clampDailyLimit(3)).toBe(3)
  })

  it('休みの日は、今日から 1 年先までを読む', () => {
    expect(closedDaysRange('2026-10-27')).toEqual({ from: '2026-10-27', to: '2027-10-27' })
  })

  it('予約が入っていた（409）ときだけ、件数を取り出す', () => {
    const has = new ApiError(409, 'visit_day_has_reservations', 'error.x', { count: 2 })
    expect(reservationCountOf(has)).toBe(2)
    expect(reservationCountOf(new ApiError(422, 'validation_error', 'error.x'))).toBeNull()
    expect(reservationCountOf(new Error('x'))).toBeNull()
  })

  it('取り消しの理由は必須で、200 文字まで（前後の空白は数えない）', () => {
    expect(reasonProblem('  ')).toBe('empty')
    expect(reasonProblem('感染症のため')).toBeNull()
    expect(reasonProblem('あ'.repeat(200))).toBeNull()
    expect(reasonProblem('あ'.repeat(201))).toBe('too_long')
  })

  it('管理画面のトップには、事務員・生活相談員・施設長にだけ出す', () => {
    for (const role of ['clerk', 'counselor', 'director'] as const) {
      expect(adminMenuFor(role).map((item) => item.to)).toContain('/admin/visit-settings')
    }
    for (const role of ['care_worker', 'leader'] as const) {
      expect(adminMenuFor(role).map((item) => item.to)).not.toContain('/admin/visit-settings')
    }
  })
})

describe('SettingsFormView', () => {
  it('選べる時刻を並べ、今の候補にチェックを付ける', () => {
    const html = renderForm()
    const boxes = html.match(/<input type="checkbox"[^>]*>/g) ?? []

    expect(boxes).toHaveLength(12)
    expect(boxes.filter((box) => box.includes('checked=""'))).toHaveLength(2)
    expect(html).toContain('10:00')
    expect(html).toContain('15:30')
  })

  it('今の組数を出す', () => {
    expect(renderForm()).toContain('2<ruby>組')
  })

  it('保存中は押せず、保存したら知らせる', () => {
    expect(renderForm({ saving: true })).toMatch(/<button type="submit" disabled=""/)
    expect(renderForm({ saved: true })).toContain('保存')
  })

  it('候補が 1 つもないときは、保存できず、案内を出す', () => {
    const html = renderForm({ initial: { daily_limit: 2, start_times: [] } })

    expect(html).toMatch(/<button type="submit" disabled=""/)
    expect(html).toContain('role="alert"')
  })
})

describe('ClosedDaysView', () => {
  it('休みの日がなければ、そう伝える', () => {
    expect(renderDays()).toContain('ありません')
  })

  it('休みの日を日付と曜日で並べ、やめるボタンを付ける', () => {
    const html = renderDays({ days: [{ id: 5, closed_date: '2026-12-31' }] })

    expect(html).toContain('12<ruby>月')
    expect(html).toContain('31<ruby>日')
    // 曜日は、家族の画面（MyVisits）と同じく、かっこの中に 1 文字で出す
    expect(html).toContain('（木）')
    expect(html).toContain('みをやめる')
  })

  it('今日より前の日は選べない', () => {
    expect(renderDays()).toContain('min="2026-10-27"')
  })

  it('予約が入っている日は、件数と理由の入力を出す（理由が空なら押せない）', () => {
    const html = renderDays({ pending: { date: '2026-11-03', count: 2 } })

    expect(html).toContain('role="alert"')
    expect(html).toContain(' 2 ')
    expect(html).toContain('<textarea')
    // 理由がまだ空なので、取り消して休みにするボタンは押せない
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>.*?取/)
  })

  it('休みにしたときは、取り消した件数を知らせる', () => {
    const html = renderDays({
      notice: { key: 'visit_settings.closed_notice_cancelled', count: 3 },
    })

    expect(html).toContain(' 3 ')
  })
})
