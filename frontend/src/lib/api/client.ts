import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

// Same-origin in dev (via the Vite proxy) and in prod (served by FastAPI), so
// auth cookies are sent automatically.
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: 'same-origin',
  // Looked up per call rather than captured once, so tests can stub fetch.
  fetch: (request) => globalThis.fetch(request),
})

export type Schemas = components['schemas']
