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

## Phase 2: Auth and onboarding

- **Registration never reveals whether an email is taken.** It always answers
  "check your inbox"; an existing verified user gets an "you already have an
  account" email instead. Forgot-password and resend-verification behave the
  same way.
- **Login is refused until the email is verified.** Clicking the emailed link
  both verifies and signs in, so the learner lands straight in onboarding.
- **Lockout returns a distinct 423 "try again in N minutes".** This does reveal
  that the account exists, but only after five rate-limited attempts, and a
  silent lockout would leave a learner unable to tell why their correct password
  fails.
- **Refresh-token reuse has a 10-second grace window.** Two tabs can refresh at
  once; the loser gets a 409 and retries with the cookies the winner already
  set. Reuse outside the window revokes the whole token family.
- **CSRF tokens are signed** (HMAC of a random nonce), not just compared, so a
  cookie planted from a sibling subdomain cannot pass the double-submit check.
  The check applies to every state-changing `/api` request that carries an auth
  cookie, including `/auth/refresh` and `/auth/logout`.
- **Google sign-in uses Authlib for PKCE and state, and plain httpx for the
  token exchange.** Authlib's own httpx integration is deprecated upstream. The
  profile is read from Google's userinfo endpoint over TLS rather than by
  validating an ID token locally.
- **OAuth state lives in a signed, httpOnly cookie** scoped to the callback
  path, so no server-side session store is needed.
- **Guardian consent is a recorded flag plus an email address**, as the spec
  asks, and the guardian is sent a notice with a link to the privacy notice.
  It is not a verified opt-in (the guardian does not have to click anything).
  Worth revisiting with legal advice before a real launch.
- **Date of birth, consent and the privacy notice are collected in onboarding**
  (the privacy tick is also required at registration; Google sign-ups accept it
  in onboarding). Guardian details are discarded for adults.
- **Account deletion anonymises the user row instead of dropping it**, so usage
  and billing records can still reference it. The profile, tokens and audit
  history are deleted. It is a `POST /users/me/delete` (not `DELETE`) because
  it needs a body with the typed confirmation and password.
- **Self-registration creates learners only.** Mentor sign-up arrives with the
  mentor side in Phase 8; admins are created by the seed script.
- **Provinces, grades and interests are not database enums.** They are short
  strings validated for length, with the option lists living in the frontend,
  so expanding beyond South African high schools needs no migration.
- **Rate limits are per IP address** and stored in Redis when `REDIS_URL` is
  set, in memory otherwise. In-memory limits are per process, so set
  `REDIS_URL` when running more than one worker.
- **Selects are native `<select>` elements.** On phones they open the OS
  picker, which is easier to use than a custom dropdown and costs no JavaScript.
- **A small in-house zod resolver replaces `@hookform/resolvers`**, whose
  optional peer dependencies pin zod 3 and conflict with the zod 4 that
  TanStack Router needs.
- **The onboarding form keeps every rule in one `superRefine`.** zod skips
  object-level refinements when any field fails its own check, which let a
  later step's empty field switch off the guardian rules on step one. A test
  caught it.
- **The privacy notice text is a first draft** written to match what the app
  actually does. It needs legal review before launch.
- **Projects and Mentor tabs are honest empty states** until Phases 4 and 8
  fill them in.
