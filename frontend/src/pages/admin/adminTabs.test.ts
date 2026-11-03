import { describe, expect, it } from 'vitest'
import { adminTabs, isAdminHome } from './adminMenu'

describe('管理画面のタブ（#437）', () => {
  it('先頭は「トップ」。そのあとに、その人の役割で開ける画面を並べる', () => {
    const tabs = adminTabs('clerk', 0)

    expect(tabs[0].to).toBe('/admin')
    // 事務員は、開示設定・変化の目印・職員のアカウントを開けない
    expect(tabs.map((tab) => tab.to)).not.toContain('/admin/disclosure')
    expect(tabs.map((tab) => tab.to)).toContain('/admin/messages')
  })

  it('メッセージのタブにだけ、対応待ちの件数を添える', () => {
    const tabs = adminTabs('director', 4)

    expect(tabs.find((tab) => tab.to === '/admin/messages')?.count).toBe(4)
    expect(tabs.filter((tab) => tab.count !== undefined)).toHaveLength(1)
  })

  it('役割がなければ、トップだけ', () => {
    expect(adminTabs(null, 0).map((tab) => tab.to)).toEqual(['/admin'])
  })

  it('トップのタブは、トップの画面だけで選ばれる（ほかの画面ではもとのタブが選ばれる）', () => {
    const tabs = adminTabs('director', 0)
    const home = tabs[0]
    const billing = tabs.find((tab) => tab.to === '/admin/billing')

    expect(home.isActive('/admin')).toBe(true)
    expect(home.isActive('/admin/billing')).toBe(false)
    expect(billing?.isActive('/admin/billing')).toBe(true)
  })

  it('トップかどうかは、パスの終わりの / を気にしない', () => {
    expect(isAdminHome('/admin')).toBe(true)
    expect(isAdminHome('/admin/')).toBe(true)
    expect(isAdminHome('/admin/billing')).toBe(false)
  })
})
