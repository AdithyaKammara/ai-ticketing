import createClient from 'openapi-fetch'
import type { paths } from './schema'
import type { ApiError, TokenOut } from './types'
import { useAuth } from '@/features/auth/authStore'

const AUTH_PATHS = ['/api/v1/auth/login', '/api/v1/auth/refresh', '/api/v1/auth/register']

let refreshing: Promise<boolean> | null = null

/** Refresh the access token from the HttpOnly cookie. Concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= doRefresh().finally(() => {
    refreshing = null
  })
  return refreshing
}

async function doRefresh(): Promise<boolean> {
  try {
    const res = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
    if (!res.ok) return false
    const data = (await res.json()) as TokenOut
    useAuth.getState().setSession(data.access_token, data.user)
    return true
  } catch {
    return false
  }
}

// One fetch that attaches the token and, on a 401, refreshes once and retries.
const authFetch: typeof fetch = async (input, init) => {
  const url = input instanceof Request ? input.url : String(input)
  const isAuthCall = AUTH_PATHS.some((p) => url.includes(p))
  const withToken = (token: string | null): RequestInit => {
    // openapi-fetch passes a Request; keep its headers (Content-Type!) when adding ours.
    const headers = new Headers(
      init?.headers ?? (input instanceof Request ? input.headers : undefined),
    )
    if (token) headers.set('Authorization', `Bearer ${token}`)
    return { ...init, headers, credentials: 'include' }
  }

  // A Request body can be read once; keep a copy for the retry.
  const retryInput = input instanceof Request ? input.clone() : input
  let res = await fetch(input, withToken(useAuth.getState().accessToken))
  if (res.status === 401 && !isAuthCall && (await refreshSession())) {
    res = await fetch(retryInput, withToken(useAuth.getState().accessToken))
  }
  return res
}

// Absolute same-origin base: identical in the browser, and valid for Node's Request in tests.
export const api = createClient<paths>({ baseUrl: window.location.origin, fetch: authFetch })

/** A failed API call. `body` is the backend's `{error: {code, message, details}}`. */
export class ApiRequestError extends Error {
  readonly body: unknown
  constructor(body: unknown) {
    super((body as Partial<ApiError> | undefined)?.error?.message ?? 'Request failed')
    this.body = body
  }
}

/** Return `data`, or throw the error body as an ApiRequestError. */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined) throw new ApiRequestError(result.error)
  return result.data as T
}

export function apiError(error: unknown): ApiError['error'] | null {
  const body = error instanceof ApiRequestError ? error.body : error
  if (body && typeof body === 'object' && 'error' in body) return (body as ApiError).error
  return null
}

export function errorMessage(error: unknown, fallback = 'Something went wrong'): string {
  return apiError(error)?.message ?? fallback
}
