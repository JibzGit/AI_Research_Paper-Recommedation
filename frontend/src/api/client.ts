import { API_BASE_URL } from '@/api/config'

/**
 * One issue from FastAPI's built-in 422 request-validation-error body,
 * whose `detail` field is an array of these -- distinct from the plain
 * `{ detail: string }` shape the backend's own exception handlers return
 * for 400/404/503 (see research_platform/api/exceptions.py).
 */
export interface ApiValidationIssue {
  loc: (string | number)[]
  msg: string
  type: string
}

/**
 * Structured error thrown by every apiGet() failure. Callers can branch on
 * `status` (400 business-rule violation, 404 genuinely not found, 422
 * malformed parameters, 5xx server error, 0 network failure/unreachable)
 * instead of a single generic "request failed" message -- the backend
 * deliberately keeps these distinct (see the clusters/papers API review
 * history), and collapsing them here would throw that away.
 */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  readonly validationErrors?: ApiValidationIssue[]

  constructor(status: number, detail: string, validationErrors?: ApiValidationIssue[]) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.validationErrors = validationErrors
  }
}

export type QueryParamValue = string | number | boolean | undefined | null

function buildQueryString(params?: Record<string, QueryParamValue>): string {
  if (!params) return ''
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

function isValidationIssueArray(value: unknown): value is ApiValidationIssue[] {
  return (
    Array.isArray(value) &&
    value.every((item) => typeof item === 'object' && item !== null && 'msg' in item && 'loc' in item)
  )
}

function formatValidationDetail(issues: ApiValidationIssue[]): string {
  return issues.map((issue) => `${issue.loc.join('.')}: ${issue.msg}`).join('; ')
}

async function parseErrorBody(response: Response): Promise<ApiError> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    return new ApiError(response.status, response.statusText || 'Request failed')
  }

  const rawDetail = body && typeof body === 'object' && 'detail' in body ? (body as { detail: unknown }).detail : undefined

  if (isValidationIssueArray(rawDetail)) {
    return new ApiError(response.status, formatValidationDetail(rawDetail), rawDetail)
  }
  if (typeof rawDetail === 'string') {
    return new ApiError(response.status, rawDetail)
  }
  return new ApiError(response.status, response.statusText || 'Request failed')
}

/**
 * GET-only by design: every endpoint this API currently exposes is a
 * read-only GET, and this frontend phase adds no mutations.
 */
export async function apiGet<T>(path: string, params?: Record<string, QueryParamValue>): Promise<T> {
  const url = `${API_BASE_URL}${path}${buildQueryString(params)}`

  let response: Response
  try {
    response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })
  } catch {
    // status 0 is a sentinel for "never reached the server" (DNS/connection
    // failure), distinct from a real HTTP status the server chose to send.
    throw new ApiError(0, 'Unable to reach the API -- check that the backend is running')
  }

  if (!response.ok) {
    throw await parseErrorBody(response)
  }

  return (await response.json()) as T
}
