# Decisions

Choices made where the build prompt (`mentor-pilot-prompt.md`) was ambiguous or
where the tooling forced a deviation. Newest phase last.

## Phase 1: Foundation

- **TypeScript 5.9, not 6.** `create-vite` now scaffolds TypeScript 6, but
  `openapi-typescript` (which keeps frontend types in step with the API) only
  supports TypeScript 5. Revisit when it adds TS 6 support.
- **oxlint instead of ESLint.** It is what the current Vite template ships with
  and is much faster. The `jsx-a11y` plugin is enabled for accessibility checks.
- **shadcn/ui on Radix primitives** (`radix-nova` style), restyled with our own
  tokens in `frontend/src/index.css`. A `touch` button size (44px) was added
  because the stock sizes are below the tap-target minimum in the spec.
- **Fonts are self-hosted** (Figtree for text, Bricolage Grotesque for headings,
  via `@fontsource-variable`). No requests to Google Fonts: better for privacy
  (POPIA, minors), for the CSP, and for offline use.
- **No inline scripts.** The theme is applied before first paint by
  `frontend/public/theme-init.js` so the CSP can stay `script-src 'self'`.
- **Dependencies are added in the phase that first uses them**, rather than all
  at once, so each phase's lockfile change is reviewable.
- **The engine lives on `app.state`**, created in the lifespan, instead of being
  a module-level global. Tests build an app against the test database with no
  monkeypatching.
- **Middleware is pure ASGI**, not `BaseHTTPMiddleware`, because the latter
  interferes with streaming responses, which the chat (SSE) depends on.
- **API docs live at `/api/docs`** and are disabled in prod, along with the
  OpenAPI schema.
- **SPA fallback returns 404 for missing files with an extension** (for example
  `/favicon.ico`) rather than `index.html`, so browsers never parse the app
  shell as an image or script.
- **`routeTree.gen.ts` and `schema.d.ts` are committed.** Both are generated,
  but committing them lets `tsc` run without a dev server or a running API.
- **Local Postgres, not Docker, on the primary dev machine.** `docker-compose.yml`
  is provided for other setups; the defaults (`mentor`/`mentor`,
  `mentor_pilot`, `mentor_pilot_test`) are the same either way.
- **`make build` was not run during development** (project rule: no builds
  unless asked). SPA serving is covered by backend tests against a stand-in
  static directory instead.
