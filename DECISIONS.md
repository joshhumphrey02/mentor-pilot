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

## Phase 3: AI provider layer

- **Adapters raise `ProviderError`; `AIService` turns it into the `Error`
  event.** The spec lists `Error` among the stream events. Keeping raising
  inside the adapter and conversion in one place means retry policy and
  learner-facing wording live in the service, not in three adapters.
- **Retries stop once the first event has been yielded.** A transient failure
  before any output is retried with backoff (tenacity). After text has started
  streaming, replaying would show the learner the same words twice, so the
  stream ends with a friendly error instead.
- **Assistant turns carry an opaque `provider_state`.** Claude's thinking blocks
  and Gemini's thought signatures must be sent back exactly as received with
  tool results. The neutral message shape cannot hold them, so each adapter
  stashes its native turn and reuses it only when the same provider and model
  see it again. History from a different provider falls back to plain text, so
  switching `AI_PROVIDER` mid-conversation works.
- **`temperature` is optional and not sent to Anthropic.** Current Claude models
  reject non-default sampling parameters. The OpenAI adapter sends it and, if a
  model rejects it, retries without and remembers.
- **Anthropic: thinking is left at the model default and
  `eager_input_streaming` is off.** We never display partial tool input, and
  leaving it off means the API validates tool input against the schema.
  Server-side refusal fallbacks are not enabled either, because the model id
  comes from the environment and the feature is model-specific; a refusal is
  surfaced as a `refusal` stop reason for the chat layer to handle kindly.
- **OpenAI uses the Chat Completions API**, the most widely supported surface
  for streaming with tools.
- **Model ids and prices for OpenAI and Gemini are not filled in.** I could not
  verify current ids or prices from a reliable source, so `.env.example` links
  to each vendor's model page and `pricing.yaml` ships with Anthropic only.
  Unpriced models record tokens with a null cost rather than a wrong one.
- **Prices live in `pricing.yaml`, not code**, with an env override, so they can
  change without a deploy of new logic.
- **Health checks call each vendor's "list/get model" endpoint** rather than
  generating text: it verifies the key (and, for the active provider, that
  `AI_MODEL` exists) without spending tokens.
- **Moderation fails closed by default.** If the check cannot be completed, the
  message is blocked (`MODERATION_FAIL_CLOSED`). Providers without a
  moderation endpoint ask the fast model to classify, with the text wrapped
  and escaped so it cannot pose as instructions.
- **A `fake` provider ships in the app, not just the tests**, so the product can
  be run and demoed with no API key. It is refused in production.
- **Adapters are tested against fake HTTP servers speaking each vendor's wire
  format**, so the real SDKs' parsing is exercised. No live call was made
  during development (no keys were available); `tests/ai/test_live.py` does
  that once keys are set.
- **`ai_usage.project_id` has no foreign key yet**; it gains one when projects
  arrive in Phase 4.

## Phase 4: Chat core

- **Callouts and suggested replies are written inline by the model as `:::`
  directives; data-heavy blocks will come from tools (Phase 5).** A tool call
  costs an extra model round trip, which is wasteful for a one-line callout
  and for reply chips at the end of every message. A streaming parser turns
  the directives into typed blocks and never lets raw syntax reach the screen.
- **A turn runs in a background task, not in the request.** The HTTP response
  only relays its events. If the connection drops, the reply still completes
  and is saved, and the client polls `GET /messages/{id}` (the id arrives in
  the first event) until it is ready.
- **One turn per conversation is enforced in the database**: the conversation
  row is locked while checking for a reply still marked `streaming`. A reply
  stuck in that state for three minutes is treated as dead, so a crash cannot
  lock a chat.
- **Replies stream before output moderation has run**, then the saved message
  replaces what was streamed. Holding the whole reply back until it was
  checked would remove streaming entirely. A flagged reply is therefore
  briefly visible on that one screen before being swapped for a redirect; it
  is never saved or shown again. Input moderation does run first, so unsafe
  input never reaches the model.
- **History is rebuilt from each message's stored raw text**, most recent 40
  messages. Blocked messages, failed replies and canned redirects are left
  out. Older context will reach the model through the project memory summary
  (Phase 5).
- **Conversation titles come from the fast model** after the first exchange,
  falling back to the learner's own opening words if that call fails.
- **Regenerate replaces the latest reply** rather than keeping alternatives.
- **Markdown images are disabled.** Images will only come through the gallery
  block, whose sources we choose, not from URLs the model writes.
- **The workspace is a full-screen route (`/project/$id`) without the tab bar**,
  so the chat gets the whole height on a phone. Its height tracks the visual
  viewport so the header and input stay on screen when the keyboard opens.
- **Enter sends on a physical keyboard and makes a new line on touch screens**,
  where there is a send button under the thumb.
- **New project is one tap, with no form.** The mentor's first questions shape
  the project, and it gets its real title when an idea is chosen.
- **The event stream is documented in OpenAPI as `ChatStreamEvents`** so the
  frontend's event payloads are generated types. The generated docs list its
  content type as JSON rather than `text/event-stream`; the description says
  what it really is.
- **Demo accounts use `@demo.example.com`.** The email validator rejects
  reserved test domains such as `.test`, which made the first seeded accounts
  impossible to log in with.

## Phase 5: Mentor intelligence

- **Stage definitions ship as YAML and live in a table.** `pathway/stages.yaml`
  is loaded into `stage_definitions` the first time the app starts with that
  table empty. After that the table is the source of truth (admins edit it in
  Phase 8) and the file is never re-applied, so edits survive restarts.
- **The model proposes a stage change; the learner confirms it.** `advance_stage`
  only shows a card. `POST /projects/{id}/stages/advance` moves the project,
  and carries the stage the card was for, so a stale card cannot skip a stage.
  `select_idea` is the one tool that moves a stage directly, because the spec
  says it does and it only runs on the learner's explicit choice.
- **Tool arguments are Pydantic models, and for display tools the arguments are
  the block.** The model fills in the structure, the schema validates it and
  the UI renders it. Invalid calls are returned to the model with the reasons,
  so it can correct itself within the round limit (5 rounds; the last offers
  no tools so the model must finish in words).
- **Tool schemas are inlined** (no `$ref`/`$defs`) so one schema works across
  all three providers.
- **Past tool use is replayed to the model as `[Record: ...]` notes**, not as
  tool calls. That keeps stored history provider-neutral and small, and the
  prompt tells the model never to write such lines itself.
- **The system prompt is built once per turn**, even though a tool may change
  the stage mid-turn. Tool results tell the model what changed, and an
  unchanging prompt keeps provider caching and thinking-block rules happy.
- **Checklist blocks store only the stage key** and render live state, so a
  tick made anywhere (in a message, in the pathway sheet, or by the mentor)
  shows everywhere.
- **Project memory is refreshed every 12 messages by the fast model**, across
  all chats in the project, capped at 2000 characters. A failed refresh keeps
  the old summary and is retried after the next turn.
- **Photos come from Wikimedia Commons with a keyword filter.** Commons is an
  open archive, not a children's collection; results whose title or
  description match an unsuitable-content list are dropped, and such queries
  are refused. This is a filter, not a guarantee. The model is told it has not
  seen the photos, so it does not describe them.
- **Video search exists only when `YOUTUBE_API_KEY` is set**; otherwise the tool
  is not offered to the model at all. It uses strict safe search, and videos
  play from the no-cookie domain only after a card is tapped.
- **Mermaid runs in `strict` security mode**, since the diagram source is model
  output. Mermaid and Recharts are separate lazy chunks.
- **The experiment plan's data table is display-only for now.** Filling it in
  inside the app arrives with experiment datasets in Phase 7.
- **Not in this phase:** `render_circuit` (Phase 6), `judge_practice` (Phase 7)
  and `request_human_mentor` (Phase 8) are added with the features they need.

## Phase 6: Signature visuals

- **One circuit block holds both the correct wiring and an optional `mistake`**
  rather than a `mode` field, so the Do/Don't switch has both versions to hand.
- **Circuits are checked electrically on the server before they are shown.**
  Models miscount breadboard holes, and a wrong circuit teaches the mistake.
  The checks catch legs sharing a strip, dangling leads, a rail-to-rail short,
  an LED with no resistor and two legs in one hole. They are construction
  checks, not a circuit simulator: a reversed LED, for example, passes. The
  `mistake` version is only checked for being drawable.
- **Breadboard view only for now.** The spec also names a `schematic` view. The
  block has no `view` field yet; a schematic renderer is a separate drawing
  problem and was left out to do the breadboard properly.
- **The board is the common half-size model** (30 columns, A-E and F-J, two
  rails per side), the same in `backend/app/ai/circuits.py` and
  `frontend/src/features/circuit/geometry.ts`. Rail holes may be written
  `+top` or `+top:5`; friendly aliases (`+rail`, `GND`, `5V`) are normalised.
- **The drawing is cropped to the columns in use** (minimum 12), so holes are
  about 24px apart on a phone instead of 10. Both versions share one crop so
  the picture does not jump when switching.
- **Step-through text is generated from the wiring**, not written by the model,
  so the words cannot disagree with the picture. The model adds an optional
  teaching note per part.
- **Parts are drawn from above, as they look pushed into the board**, and each
  is a focusable control with a text label; the whole build is also available
  as a text list. Board colours are those of the physical object and are not
  themed.
- **Animation is CSS, not the `motion` library.** The reveal, step placement and
  LED glow are opacity and transform transitions, which need no JavaScript
  library. `motion` has not been added; it can be if a later phase needs
  gesture-driven animation.
- **Component photos are looked up from Wikimedia Commons on first tap and
  cached in memory per process.** A failed lookup is not cached.
- **The fake provider has one canned demo**: asking how to connect an LED on a
  breadboard produces the reference circuit, so the feature can be shown with
  no API key.
- **Verified by rendering.** There is no browser in the development
  environment, so the SVG was rendered to an image and inspected in its Do,
  Don't and Reveal states. Touch behaviour on a real phone is untested.

## Phase 7: Workspace extras

- **Uploads are identified by their first bytes**, not the filename or the
  type the browser declares. JPEG, PNG and WebP only, 5 MB by default, stored
  under a server-chosen name and served with a sandboxing CSP. SVG is refused
  because it can carry script.
- **Storage is local disk behind a three-method interface** (`services/storage.py`).
  The S3-compatible backend the spec mentions is not written; it must be
  before running more than one server, since local disk is not shared.
- **Only the newest message's photos are sent to the model as images.** Earlier
  ones are replaced by a short note in the history, because resending images
  every turn is expensive. Providers without vision get the note instead.
- **A message needs text; a photo alone is sent with a default sentence**
  ("Here is a photo. What do you think?"), which keeps the API rule simple.
- **Judge practice is one tool with two actions.** `start` returns the rules of
  judge mode to the model (one question at a time, no coaching); `score` shows
  a rubric scorecard. The questioning itself is ordinary conversation.
- **Pins store a copy of the block**, so a saved diagram survives the reply it
  came from being regenerated. Reply chips, errors, stage cards and the
  learner's own photos cannot be pinned.
- **Editing a logbook entry keeps its original date.**
- **Datasets hold cell text exactly as typed.** Numbers are parsed only when
  charting, and a decimal comma is accepted. The first column is the x axis.
- **The PDF uses the built-in Latin-1 fonts** to avoid shipping a font file, so
  typographic characters are swapped for plain ones (curly quotes, arrows, Ω
  becomes "ohm"). Text in scripts outside Latin-1 would print as "?"; bundle a
  Unicode font when other languages are added. Charts and diagrams are not
  drawn in the PDF: data appears as tables and other saved items are listed.
- **Voice input uses the browser's Web Speech API** (`en-ZA`) and the button is
  hidden where it is unsupported. In Chrome the audio is processed by Google's
  speech service, which is worth stating in the privacy notice before launch.
- **Not verified in a browser:** the camera/photo picker, dictation and the
  bottom sheet were exercised only through component tests.

## Phase 8: Mentor handoff and admin

- **The AI offers a human mentor; the learner sends the request.** As with
  stage changes, the model shows a card and nothing happens until the learner
  acts. One open request per project.
- **Mentors must be approved by an admin** before they can see or accept any
  request. Sign-up is open; access to learners is not. This is a manual vetting
  step: the app records the approval, it does not perform background checks.
- **Learner and mentor see only each other's first name.** A request carries a
  snapshot of the project (title, stage, idea, summary) instead of giving the
  mentor access to the learner's conversations.
- **Contact details are refused in learner-mentor messages** (phone numbers,
  emails, links, social handles) and every message is moderated. The filter is
  pattern-based and can be evaded by a determined person; it sets the norm and
  catches the ordinary case. Meetings are meant to be arranged through the
  school.
- **Matching is by province and help type.** Admins can assign by hand.
- **No real-time messaging.** An open thread polls every 15 seconds.
- **Credits are counted, not enforced.** Each learner has a monthly allowance of
  mentor replies (`FREE_TURNS_PER_MONTH`, default 200) plus any credits granted
  in the ledger to them or their school. `ENFORCE_CREDITS` exists as a setting
  but nothing reads it yet: with no way to pay, blocking would only lock
  learners out.
- **Payments are an interface with a stub** (`services/payments.py`). PayFast,
  Yoco and Paystack are the candidates.
- **Stage editing in the admin UI covers the goal and the mentoring
  instructions.** The API also accepts the title, checklist and exit criteria.
  Removing a checklist item leaves any existing ticks for it in place, unused.
- **Endpoints must have unique function names.** They double as OpenAPI
  operation ids; two `list_messages` functions made the generated client mix
  up their types. A test now enforces uniqueness.
- **The admin UI is functional rather than polished**, as the spec asks: tables
  and simple actions, with the learner experience as the priority.
