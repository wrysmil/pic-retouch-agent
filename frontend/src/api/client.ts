export type StructuredDetail = {
  code?: string
  message?: string
  available?: number
  required?: number
  reset_at?: string
  scope?: string
  limit?: number
  window_seconds?: number
  retry_after_seconds?: number
  retry_after_ms?: number
}

export class ApiError extends Error {
  status: number
  code: string | null
  detail: StructuredDetail | null
  retryAfterSeconds: number

  constructor(
    status: number,
    message: string,
    code: string | null = null,
    detail: StructuredDetail | null = null,
    retryAfterSeconds = 0,
  ) {
    super(message)
    this.status = status
    this.code = code
    this.detail = detail
    this.retryAfterSeconds = retryAfterSeconds
  }
}

// pydantic 会给自定义校验加这个前缀，对用户没有意义
const VALUE_ERROR = /^Value error,\s*/

function messageOf(item: unknown): string {
  if (typeof item === 'string') return item.trim()
  if (!item || typeof item !== 'object') return ''
  const { msg, message } = item as { msg?: unknown; message?: unknown }
  return messageOf(msg ?? message).replace(VALUE_ERROR, '')
}

/** FastAPI 校验失败时 detail 是 `{loc, msg, type}` 数组，原样当字符串会渲染成 [object Object]。 */
function formatDetail(detail: unknown, fallback: string): string {
  if (Array.isArray(detail)) {
    return detail.map(messageOf).filter(Boolean).join('；') || fallback
  }
  return messageOf(detail) || fallback
}

function retryAfter(response: Response, detail: StructuredDetail | null) {
  if (typeof detail?.retry_after_seconds === 'number') return detail.retry_after_seconds
  const header = Number(response.headers.get('Retry-After'))
  return Number.isFinite(header) && header > 0 ? header : 0
}

/** 上传与下载走原生 fetch，错误一律经这里构造，文案格式与 JSON 请求保持一致。 */
export async function apiError(response: Response, fallback: string): Promise<ApiError> {
  const body = await response.json().catch(() => null)
  const detail = body?.detail
  // 业务错误用对象 detail 带上 code 与额度信息；逻辑判断只看 code，不匹配中文字符串
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const typed = detail as StructuredDetail
    return new ApiError(
      response.status,
      messageOf(detail) || fallback,
      typeof typed.code === 'string' ? typed.code : null,
      typed,
      retryAfter(response, typed),
    )
  }
  return new ApiError(response.status, formatDetail(detail, fallback))
}

export function isQuotaExhausted(error: unknown): error is ApiError {
  return error instanceof ApiError && error.code === 'QUOTA_EXHAUSTED'
}

export function isRateLimited(error: unknown): error is ApiError {
  return (
    error instanceof ApiError &&
    (error.code === 'RATE_LIMITED' || error.code === 'SSE_CONNECTION_LIMIT')
  )
}

export function isAuthLocked(error: unknown): error is ApiError {
  return error instanceof ApiError && error.code === 'AUTH_LOCKED'
}

export function rateLimitSeconds(error: unknown): number {
  return isRateLimited(error) || isAuthLocked(error) ? Math.max(1, error.retryAfterSeconds) : 0
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) throw await apiError(response, response.statusText)
  return response.status === 204 ? (undefined as T) : response.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
