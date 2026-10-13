import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { render } from '@testing-library/react'
import { vi } from 'vitest'

import { routeTree } from '@/routeTree.gen'

type Handler = (request: Request) => Response | Promise<Response>

/** Routes keyed by "METHOD /path", e.g. "POST /api/v1/auth/login". */
export type Handlers = Record<string, Handler>

export const json = (body: unknown, status = 200) => Response.json(body, { status })

export const apiError = (status: number, code: string, detail = 'Something went wrong.') =>
  json({ detail, code }, status)

export const student = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'thandi@example.com',
  full_name: 'Thandi Mokoena',
  role: 'student',
  preferred_language: 'en',
  is_verified: true,
  is_onboarded: true,
  has_password: true,
  privacy_accepted: true,
  created_at: '2026-01-01T00:00:00Z',
  student_profile: null,
}

const DEFAULTS: Handlers = {
  'GET /api/v1/users/me': () => apiError(401, 'not_authenticated'),
  'GET /api/v1/auth/providers': () => json({ google: false }),
}

/** Replaces fetch with an in-memory API and records the requests made to it. */
export function mockApi(handlers: Handlers = {}) {
  const routes = { ...DEFAULTS, ...handlers }
  const calls: Request[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init)
      calls.push(request.clone())
      const key = `${request.method} ${new URL(request.url).pathname}`
      const handler = routes[key]
      if (!handler) throw new Error(`Unmocked request: ${key}`)
      return handler(request)
    }),
  )
  return {
    calls,
    count: (key: string) =>
      calls.filter((call) => `${call.method} ${new URL(call.url).pathname}` === key).length,
  }
}

/** Renders the whole app at a URL, with real routing and guards. */
export function renderApp(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createRouter({
    routeTree,
    context: { queryClient },
    history: createMemoryHistory({ initialEntries: [path] }),
  })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router as never} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}
