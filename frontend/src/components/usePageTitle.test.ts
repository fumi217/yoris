import { describe, expect, it } from 'vitest'
import { pageTitle } from './usePageTitle'

describe('pageTitle', () => {
  it('「画面の題 ｜ YORIS」にする（2.4.2）', () => {
    expect(pageTitle('連絡帳', 'YORIS')).toBe('連絡帳 ｜ YORIS')
  })

  it('ふりがなの書き方は外して、漢字だけにする（タブの題にはルビを出せない）', () => {
    expect(pageTitle('{職員|しょくいん}の{画面|がめん}', 'YORIS')).toBe('職員の画面 ｜ YORIS')
  })

  it('画面の題がなければ、アプリの名前だけ', () => {
    expect(pageTitle(null, 'YORIS')).toBe('YORIS')
    expect(pageTitle(undefined, 'YORIS')).toBe('YORIS')
    expect(pageTitle('  ', 'YORIS')).toBe('YORIS')
  })
})
