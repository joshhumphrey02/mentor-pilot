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

/** How an attempt to renew the session ended. */
type Refresh = 'renewed' | 'signed-out' | 'unreachable'

let refreshing: Promise<Refresh> | null = null

/**
 * Swaps the refresh cookie for a new session. Calls made while one is already
 * in flight share it, because each refresh token can only be used once.
 *
 * Only the server saying so counts as signed out. A dropped connection, a
 * restarting server or a rate limit says nothing about the session.
 */
export function refreshSession(): Promise<Refresh> {
  refreshing ??= (async (): Promise<Refresh> => {
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
      if (response.ok || response.status === 409) return 'renewed'
      return response.status === 401 || response.status === 403 ? 'signed-out' : 'unreachable'
    } catch {
      return 'unreachable'
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

/** Stands in for a reply when the session could not be renewed for now. */
const unreachable = () =>
  Response.json(
    { detail: "We couldn't reach Mentor Pilot. Check your connection and try again.", code: 'unavailable' },
    { status: 503 },
  )

async function isStaleCookies(response: Response): Promise<boolean> {
  if (response.status !== 403) return false
  const body: unknown = await response.clone().json().catch(() => null)
  return (
    typeof body === 'object' && body !== null && 'code' in body && body.code === 'csrf_failed'
  )
}

/** fetch, plus the CSRF header, plus one silent retry after refreshing an expired session. */
export async function authFetch(request: Request): Promise<Response> {
  const retry = request.clone()
  let response = await globalThis.fetch(withCsrf(request.clone()))
  if (await isStaleCookies(response)) {
    // The server has just removed cookies it no longer recognises (its secret
    // key changed). Without them the same request is judged on its own merits.
    response = await globalThis.fetch(withCsrf(request))
  }
  if (response.status !== 401 || NO_REFRESH.test(new URL(request.url).pathname)) return response
  const refresh = await refreshSession()
  if (refresh === 'signed-out') return response
  // Passing the 401 on here would tell the app its user had signed out.
  if (refresh === 'unreachable') return unreachable()
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

/** Opens a streaming POST (Server-Sent Events) with the same auth handling as `api`. */
export function openStream(path: string, body?: unknown): Promise<Response> {
  return authFetch(
    new Request(new URL(path, window.location.origin), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  )
}
