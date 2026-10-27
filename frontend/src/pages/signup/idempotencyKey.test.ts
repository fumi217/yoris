import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearIdempotencyKey, getIdempotencyKey } from './idempotencyKey'

function fakeStorage(initial: Record<string, string> = {}) {
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

afterEach(() => {
  clearIdempotencyKey()
  vi.unstubAllGlobals()
})

describe('getIdempotencyKey', () => {
  it('作った値を残し、何度呼んでも同じ値を返す（二度押し・2 つのタブ）', () => {
    const storage = fakeStorage()
    vi.stubGlobal('localStorage', storage)

    const first = getIdempotencyKey()

    expect(first).not.toBe('')
    expect(getIdempotencyKey()).toBe(first)
    expect(Object.values(storage.data)).toEqual([first])
  })

  it('ほかのタブが残した値を使う', () => {
    vi.stubGlobal('localStorage', fakeStorage({ 'signup.idempotencyKey': 'from-other-tab' }))

    expect(getIdempotencyKey()).toBe('from-other-tab')
  })

  it('消したあとは、新しい値を作る', () => {
    vi.stubGlobal('localStorage', fakeStorage())
    const first = getIdempotencyKey()

    clearIdempotencyKey()

    expect(getIdempotencyKey()).not.toBe(first)
  })

  it('onlyIf を渡したときは、残っている値が同じときだけ消す（別のタブの新しい値を守る）', () => {
    const storage = fakeStorage({ 'signup.idempotencyKey': 'new-tab-key' })
    vi.stubGlobal('localStorage', storage)

    clearIdempotencyKey('old-key')
    expect(getIdempotencyKey()).toBe('new-tab-key')

    clearIdempotencyKey('new-tab-key')
    expect(storage.data).toEqual({})
  })

  it('localStorage が使えなくても、画面を開いている間は同じ値を使う', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
      removeItem: () => {
        throw new Error('blocked')
      },
    })

    const first = getIdempotencyKey()

    expect(getIdempotencyKey()).toBe(first)
    expect(() => clearIdempotencyKey()).not.toThrow()
  })
})
