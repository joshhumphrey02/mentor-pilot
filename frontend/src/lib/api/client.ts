import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

const CSRF_COOKIE = 'mp_csrf'
const CSRF_HEADER = 'X-CSRF-Token'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])
const REFRESH_URL = '/api/v1/auth/refresh'
// A 401 from these means "wrong credentials", not "session expired".
const NO_REFRESH = /\/api\/v1\/auth\/(login|register|refresh|logout|verify-email|reset-password)$/

function readCookie(name: string): string | null {
  const match = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null
}

function withCsrf(request: Request): Request {
  if (!SAFE_METHODS.has(request.method)) {
    const token = readCookie(CSRF_COOKIE)
    if (token) request.headers.set(CSRF_HEADER, token)
  }
  return request
}

let refreshing: Promise<boolean> | null = null

/**
 * Swaps the refresh cookie for a new session. Calls made while one is already
 * in flight share it, because each refresh token can only be used once.
 */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const response = await globalThis.fetch(
        withCsrf(
          new Request(new URL(REFRESH_URL, window.location.origin), {
            method: 'POST',
            credentials: 'same-origin',
          }),
        ),
      )
      // 409: another tab refreshed a moment ago and already set new cookies.
      return response.ok || response.status === 409
    } catch {
      return false
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

/** fetch, plus the CSRF header, plus one silent retry after refreshing an expired session. */
async function authFetch(request: Request): Promise<Response> {
  const retry = request.clone()
  const response = await globalThis.fetch(withCsrf(request))
  if (response.status !== 401 || NO_REFRESH.test(new URL(request.url).pathname)) return response
  if (!(await refreshSession())) return response
  return globalThis.fetch(withCsrf(retry))
}

// Same-origin in dev (via the Vite proxy) and in prod (served by FastAPI), so
// auth cookies are sent automatically.
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: 'same-origin',
  fetch: authFetch,
})

export type Schemas = components['schemas']
