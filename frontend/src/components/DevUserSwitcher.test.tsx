import { QueryClient } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import '../i18n'
import { api } from '../api/client'
import { DevSwitcherShell } from './DevUserSwitcher'
import { switchDevUser } from './devSwitch'

vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  api: { get: vi.fn(), post: vi.fn() },
}))

function shell(open: boolean, inFamily = true) {
  return renderToStaticMarkup(
    <DevSwitcherShell open={open} inFamily={inFamily} onToggle={() => {}} onSubmit={() => {}}>
      <span>中身</span>
    </DevSwitcherShell>,
  )
}

describe('DevSwitcherShell', () => {
  it('閉じているとき：アイコンを出し、シート（フォーム）は幅 1280px 未満では隠す', () => {
    const html = shell(false)

    expect(html).toMatch(/aria-expanded="false"/)
    const form = html.match(/<form[^>]*class="([^"]*)"/)?.[1].split(' ')
    expect(form).toContain('hidden')
    expect(form).toContain('xl:block')
    expect(html).toMatch(/<button[^>]*class="[^"]*xl:hidden[^"]*"[^>]*><svg/)
  })

  it('開いているとき：シートを出し、アイコンは開いている印になる', () => {
    const html = shell(true)

    expect(html).toMatch(/aria-expanded="true"/)
    const form = html.match(/<form[^>]*class="([^"]*)"/)?.[1].split(' ')
    expect(form).toContain('block')
    expect(form).not.toContain('hidden')
    expect(html).toContain('中身')
  })

  it('シートの中に、閉じる「×」がある（幅 1280px 以上では隠す）', () => {
    expect(shell(true)).toMatch(
      /aria-label="閉じる"[^>]*class="xl:hidden"|class="xl:hidden"[^>]*aria-label="閉じる"/,
    )
  })

  it('家族の画面は下のメニューの上、ほかの画面は画面の下から少し上に置く', () => {
    expect(shell(false, true)).toContain('bottom-[calc(var(--family-menu-height)+1rem)]')
    expect(shell(false, false)).toMatch(/\bbottom-4\b/)
  })

  it('幅 1280px 以上は、右下に今までの高さで出す', () => {
    expect(shell(false)).toContain('xl:right-2')
    expect(shell(false)).toContain('xl:bottom-[calc(var(--family-menu-height)+5.5rem)]')
  })
})

describe('switchDevUser', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset()
  })

  it('切り替えたら、シートを閉じ、前の人のデータを捨てて、最初の画面へ移る（人の一覧は残す）', async () => {
    vi.mocked(api.post).mockResolvedValue({})
    const queryClient = new QueryClient()
    queryClient.setQueryData(['dev', 'users'], [])
    queryClient.setQueryData(['me'], { kind: 'family' })
    const close = vi.fn()
    const navigate = vi.fn()

    const result = await switchDevUser(3, { queryClient, navigate, close })

    expect(result).toBeNull()
    expect(api.post).toHaveBeenCalledWith('/api/dev/switch-user', { user_id: 3 })
    expect(close).toHaveBeenCalledOnce()
    expect(navigate).toHaveBeenCalledWith('/')
    expect(queryClient.getQueryData(['dev', 'users'])).toEqual([])
    expect(queryClient.getQueryData(['me'])).toBeUndefined()
  })

  it('失敗したら、シートは閉じず、移りもせず、エラーの文言のキーを返す', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('boom'))
    const close = vi.fn()
    const navigate = vi.fn()

    const result = await switchDevUser(3, { queryClient: new QueryClient(), navigate, close })

    expect(result).toEqual(expect.any(String))
    expect(close).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
  })
})
