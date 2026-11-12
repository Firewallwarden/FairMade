type ValidationIssue = { field: string; message: string }

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly issues: ValidationIssue[]

  constructor(
    message: string,
    status: number,
    code?: string,
    issues: ValidationIssue[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.issues = issues
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function responseError(status: number, body: unknown): ApiError {
  const detail = isRecord(body) ? body.detail : undefined
  if (isRecord(detail) && typeof detail.message === 'string') {
    return new ApiError(
      detail.message,
      status,
      typeof detail.code === 'string' ? detail.code : undefined,
    )
  }
  if (Array.isArray(detail)) {
    const issues = detail.filter(isRecord).map((issue) => ({
      field: Array.isArray(issue.loc)
        ? issue.loc
            .filter(
              (part) => typeof part === 'string' || typeof part === 'number',
            )
            .join('.')
        : '',
      message: typeof issue.msg === 'string' ? issue.msg : 'Invalid value',
    }))
    return new ApiError(
      'Please check the inputs and try again.',
      status,
      undefined,
      issues,
    )
  }
  // Do not surface arbitrary proxy HTML, server tracebacks, or submitted inputs.
  return new ApiError(
    status === 401
      ? 'Your session has ended. Please sign in again.'
      : `The request could not be completed (${status}).`,
    status,
  )
}

type ApiOptions = Omit<RequestInit, 'body'> & {
  json?: unknown
  token?: string
  timeoutMs?: number
  raw?: Blob
  binary?: boolean
}

export function createApiClient(
  baseUrl: string,
  fetcher: typeof fetch = fetch,
) {
  return async function request<T>(
    path: `/${string}`,
    decode: (data: unknown) => T,
    options: ApiOptions = {},
  ): Promise<T> {
    const { json, token, timeoutMs = 20000, raw, binary, ...init } = options
    const headers = new Headers(init.headers)
    headers.set('Accept', binary ? 'image/jpeg' : 'application/json')
    if (json !== undefined) headers.set('Content-Type', 'application/json')
    if (token) headers.set('Authorization', `Bearer ${token}`)
    let response: Response
    const timeout = AbortSignal.timeout(
      Math.min(180000, Math.max(1000, timeoutMs)),
    )
    try {
      response = await fetcher(`${baseUrl.replace(/\/$/, '')}${path}`, {
        ...init,
        headers,
        cache: 'no-store',
        credentials: 'omit',
        signal: init.signal ? AbortSignal.any([init.signal, timeout]) : timeout,
        body: raw ?? (json === undefined ? undefined : JSON.stringify(json)),
      })
    } catch (error) {
      if (timeout.aborted)
        throw new ApiError(
          'FairMade took too long to respond. Refresh saved status before retrying an action; its outcome may still be pending.',
          0,
          'REQUEST_TIMEOUT',
        )
      if (error instanceof Error && error.name === 'AbortError') throw error
      throw new ApiError(
        'Cannot reach FairMade. Check that the local API is running, then try again.',
        0,
      )
    }
    let body: unknown
    if (binary && response.ok) return decode(await response.blob())
    if (response.status !== 204) {
      try {
        body = await response.json()
      } catch {
        throw new ApiError(
          'FairMade returned an unreadable response. Please try again.',
          response.status,
        )
      }
    }
    if (!response.ok) throw responseError(response.status, body)
    try {
      return decode(body)
    } catch {
      throw new ApiError(
        'The API response does not match this version of FairMade. Please check the integration configuration.',
        response.status,
      )
    }
  }
}
