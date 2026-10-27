import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import '../../i18n'
import { BackToAdmin } from './AdminLayout'
import { isAdminHome } from './adminMenu'

const render = (pathname: string) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <BackToAdmin pathname={pathname} />
    </MemoryRouter>,
  )

describe('BackToAdmin', () => {
  it('トップ以外の管理画面では、いちばん上に「管理画面のトップへ」を出す（#256）', () => {
    for (const pathname of [
      '/admin/disclosure',
      '/admin/messages',
      '/admin/messages/3',
      '/admin/billing',
      '/admin/visit-settings',
    ]) {
      expect(render(pathname)).toContain('href="/admin"')
    }
  })

  it('トップでは出さない', () => {
    expect(render('/admin')).toBe('')
    expect(render('/admin/')).toBe('')
  })

  it('トップかどうかは、パスの終わりの / を気にしない', () => {
    expect(isAdminHome('/admin')).toBe(true)
    expect(isAdminHome('/admin/')).toBe(true)
    expect(isAdminHome('/admin/billing')).toBe(false)
  })
})
