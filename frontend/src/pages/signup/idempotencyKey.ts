// 申し込みの二度押し・2 つのタブ対策の値（spec 002 の T024・research.md R-12）。
//
// 申し込みページを開いたときにランダムな値を作り、`localStorage` に残す。送るたびに同じ値を付けるので、
// 二度押し・2 つのタブでも、サーバーは同じ申し込み・同じ支払い画面にまとめる。
// 申し込みが終わったとき・「戻る」で取り消したときに消して、次は新しい値を作る。
// `localStorage` が使えないとき（プライベートモードなど）は、画面を開いている間だけ同じ値を使う。

const STORAGE_KEY = 'signup.idempotencyKey'

let memoryKey: string | null = null

function newKey(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  // https でない開発環境など、randomUUID がないとき
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) =>
    b.toString(16).padStart(2, '0'),
  ).join('')
}

function read(): string | null {
  try {
    return globalThis.localStorage?.getItem(STORAGE_KEY) ?? null
  } catch {
    return null
  }
}

function write(key: string): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, key)
  } catch {
    // 使えないときは、メモリの値だけで続ける
  }
}

/** 今の申し込みの値。なければ作って残す。 */
export function getIdempotencyKey(): string {
  const saved = read()
  if (saved) return saved
  memoryKey ??= newKey()
  write(memoryKey)
  return memoryKey
}

/**
 * 申し込みが終わった・取り消したときに消す（次の申し込みは、新しい値になる）。
 * `onlyIf` を渡したときは、残っている値がそれと同じときだけ消す
 * （「戻る」で取り消した古い申し込みの値で、別のタブの新しい申し込みの値を消さないため）。
 */
export function clearIdempotencyKey(onlyIf?: string): void {
  if (onlyIf !== undefined) {
    const current = read() ?? memoryKey
    if (current !== null && current !== onlyIf) return
  }
  memoryKey = null
  try {
    globalThis.localStorage?.removeItem(STORAGE_KEY)
  } catch {
    // 使えないときは、何もしない
  }
}
