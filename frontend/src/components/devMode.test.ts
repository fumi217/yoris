import { describe, expect, it, vi } from 'vitest'
import { isDevHidden, isFamilyPath, readHiddenMark, saveHiddenMark } from './devMode'

function fakeStore(initial: Record<string, string> = {}) {
  const data = { ...initial }
  return {
    data,
    getItem: (key: string) => data[key] ?? null,
    setItem: (key: string, value: string) => {
      data[key] = value
    },
    removeItem: (key: string) => {
      delete data[key]
    },
  }
}

describe('isDevHidden', () => {
  it('印も ?dev もないときは、出す（ふだんの実装中）', () => {
    expect(isDevHidden('', false)).toBe(false)
    expect(isDevHidden('?date=2026-10-23', false)).toBe(false)
  })

  it('?dev=0 のときは隠す', () => {
    expect(isDevHidden('?dev=0', false)).toBe(true)
  })

  it('隠す印があれば、?dev がない画面でも隠れたまま', () => {
    expect(isDevHidden('', true)).toBe(true)
  })

  it('?dev=1 は、隠す印があっても出す', () => {
    expect(isDevHidden('?dev=1', true)).toBe(false)
  })

  it('dev が 0・1 以外のときは、印に従う', () => {
    expect(isDevHidden('?dev=2', true)).toBe(true)
    expect(isDevHidden('?dev=2', false)).toBe(false)
  })
})

describe('隠す印の読み書き', () => {
  it('隠すと印を覚え、出し直すと消す', () => {
    const store = fakeStore()

    saveHiddenMark(store, true)
    expect(readHiddenMark(store)).toBe(true)

    saveHiddenMark(store, false)
    expect(readHiddenMark(store)).toBe(false)
    expect(store.data).toEqual({})
  })

  it('sessionStorage が使えなくても（null・例外）、落ちずに「出す」側になる', () => {
    const broken = {
      getItem: vi.fn(() => {
        throw new Error('blocked')
      }),
      setItem: vi.fn(() => {
        throw new Error('blocked')
      }),
      removeItem: vi.fn(() => {
        throw new Error('blocked')
      }),
    }

    expect(readHiddenMark(null)).toBe(false)
    expect(readHiddenMark(broken)).toBe(false)
    expect(() => saveHiddenMark(null, true)).not.toThrow()
    expect(() => saveHiddenMark(broken, true)).not.toThrow()
    expect(() => saveHiddenMark(broken, false)).not.toThrow()
  })
})

describe('isFamilyPath', () => {
  it('/family とその下だけが家族の画面', () => {
    expect(isFamilyPath('/family')).toBe(true)
    expect(isFamilyPath('/family/inquiry')).toBe(true)
    expect(isFamilyPath('/staff/records')).toBe(false)
    expect(isFamilyPath('/familyx')).toBe(false)
  })
})
