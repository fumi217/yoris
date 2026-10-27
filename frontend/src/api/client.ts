// API を呼ぶ関数（spec 001 の T018・contracts/api.md）。画面から API を呼ぶときは、必ずここを通す。
//
//   const records = await api.get<Records>('/api/family/contact-book?date=2026-10-23')
//   await api.post('/api/family/requests', { theme_id: 1 })
//
// - 書き込み（POST・PUT・PATCH・DELETE）には `X-Requested-With: fetch` を付ける（付けないと 403。research.md R-03）
// - エラーは ApiError を投げる。画面では `t(error.messageKey)` で文言を出す（辞書の `error.<code>`）

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly messageKey: string
  // 文言に使う値（件数など）。付いているエラーだけ（例：面会の visit_day_has_reservations の count）
  readonly details: Record<string, number | string>

  constructor(
    status: number,
    code: string,
    messageKey: string,
    details: Record<string, number | string> = {},
  ) {
    super(`${status} ${code}`)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.messageKey = messageKey
    this.details = details
  }
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

type ErrorBody = {
  error?: { code?: string; message_key?: string; details?: Record<string, number | string> }
}

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  if (method !== 'GET') headers['X-Requested-With'] = 'fetch'
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'same-origin',
    })
  } catch {
    // つながらない（オフライン・サーバーが止まっている）
    throw new ApiError(0, 'server_error', 'error.server_error')
  }

  if (response.status === 204) return undefined as T
  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = (data as ErrorBody | null)?.error
    throw new ApiError(
      response.status,
      error?.code ?? 'server_error',
      error?.message_key ?? 'error.server_error',
      error?.details ?? {},
    )
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T = void>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T = void>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T = void>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T = void>(path: string) => request<T>('DELETE', path),
}

/** 画面に出す文言の辞書のキー。ApiError でないもの（画面のコードの失敗など）は server_error。 */
export function messageKeyOf(error: unknown): string {
  return error instanceof ApiError ? error.messageKey : 'error.server_error'
}
