import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiError, eventStream, json, mockApi, renderApp, student } from '@/test/app'

afterEach(() => vi.unstubAllGlobals())

const PROJECT_ID = 'p1'
const CONVERSATION_ID = 'c1'
const at = '2026-10-01T10:00:00Z'

const conversation = {
  id: CONVERSATION_ID,
  project_id: PROJECT_ID,
  title: '',
  last_message_at: at,
  created_at: at,
}
const project = {
  id: PROJECT_ID,
  title: 'Solar phone charger',
  current_stage: 'research_question',
  status: 'active',
  idea: null,
  last_activity_at: at,
  created_at: at,
  latest_conversation: conversation,
}

function message(id: string, role: 'user' | 'assistant', blocks: unknown[], extra = {}) {
  return {
    id,
    conversation_id: CONVERSATION_ID,
    role,
    status: 'complete',
    blocks,
    feedback: null,
    created_at: at,
    ...extra,
  }
}

const reply = message('m2', 'assistant', [
  { type: 'markdown', text: 'An LED lets current flow **one way**.' },
  { type: 'callout', variant: 'safety', text: 'Always use a resistor.' },
  { type: 'suggested_replies', replies: ['Show me a diagram', 'Why a resistor?'] },
])

const MESSAGES = `GET /api/v1/conversations/${CONVERSATION_ID}/messages`
const SEND = `POST /api/v1/conversations/${CONVERSATION_ID}/messages`

function workspace(handlers = {}) {
  const api = mockApi({
    'GET /api/v1/users/me': () => json(student),
    [`GET /api/v1/projects/${PROJECT_ID}`]: () => json(project),
    [MESSAGES]: () => json({ messages: [], next_before: null }),
    ...handlers,
  })
  return { ...api, ...renderApp(`/project/${PROJECT_ID}`) }
}

describe('project workspace', () => {
  it('shows the project, its stage and a welcome for a new chat', async () => {
    workspace()

    expect(await screen.findByRole('heading', { name: 'Solar phone charger' })).toBeInTheDocument()
    expect(screen.getByText('Stage 3 of 9 · Research Question')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: /Hi Thandi/ })).toBeInTheDocument()
  })

  it('streams a reply into typed blocks and offers the suggested replies', async () => {
    workspace({
      [SEND]: () =>
        eventStream([
          [
            'message_start',
            {
              user_message: message('m1', 'user', [{ type: 'markdown', text: 'How do LEDs work?' }]),
              assistant_message_id: 'm2',
            },
          ],
          ['block_start', { index: 0, type: 'markdown' }],
          ['text_delta', { index: 0, text: 'An LED lets current ' }],
          ['text_delta', { index: 0, text: 'flow **one way**.' }],
          ['block_complete', { index: 0, block: reply.blocks[0] }],
          ['block_start', { index: 1, type: 'callout' }],
          ['block_complete', { index: 1, block: reply.blocks[1] }],
          ['block_complete', { index: 2, block: reply.blocks[2] }],
          ['usage', { input_tokens: 10, output_tokens: 20 }],
          ['done', { message: reply }],
        ]),
    })

    await userEvent.type(await screen.findByLabelText('Message your mentor'), 'How do LEDs work?')
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('How do LEDs work?')).toBeInTheDocument()
    const callout = await screen.findByRole('note')
    expect(within(callout).getByText('Safety')).toBeInTheDocument()
    expect(within(callout).getByText('Always use a resistor.')).toBeInTheDocument()
    expect(await screen.findByText('one way')).toBeInTheDocument()

    const chips = await screen.findByRole('list', { name: 'Suggested replies' })
    expect(within(chips).getByRole('button', { name: 'Why a resistor?' })).toBeInTheDocument()
    expect(screen.getByLabelText('Message your mentor')).toHaveValue('')
  })

  it('sends a suggested reply when its chip is tapped', async () => {
    const sent: string[] = []
    workspace({
      [MESSAGES]: () =>
        json({
          messages: [message('m1', 'user', [{ type: 'markdown', text: 'Hi' }]), reply],
          next_before: null,
        }),
      [SEND]: async (request: Request) => {
        sent.push(((await request.json()) as { text: string }).text)
        return eventStream([['done', { message: message('m4', 'assistant', []) }]])
      },
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Why a resistor?' }))

    await waitFor(() => expect(sent).toEqual(['Why a resistor?']))
  })

  it('loads earlier messages when the page is reopened', async () => {
    workspace({
      [MESSAGES]: () =>
        json({
          messages: [message('m1', 'user', [{ type: 'markdown', text: 'Hi mentor' }]), reply],
          next_before: null,
        }),
    })

    expect(await screen.findByText('Hi mentor')).toBeInTheDocument()
    expect(await screen.findByText('Always use a resistor.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /I'm your mentor/ })).not.toBeInTheDocument()
  })

  it('recovers the reply by id when the connection drops mid-stream', async () => {
    const { count } = workspace({
      // The stream ends after message_start, with no "done": a dropped connection.
      [SEND]: () =>
        eventStream([
          [
            'message_start',
            {
              user_message: message('m1', 'user', [{ type: 'markdown', text: 'Hello' }]),
              assistant_message_id: 'm2',
            },
          ],
        ]),
      'GET /api/v1/messages/m2': () => json(reply),
    })

    await userEvent.type(await screen.findByLabelText('Message your mentor'), 'Hello')
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('Reconnecting…')).toBeInTheDocument()
    expect(
      await screen.findByText('Always use a resistor.', undefined, { timeout: 4000 }),
    ).toBeInTheDocument()
    expect(count('GET /api/v1/messages/m2')).toBe(1)
  })

  it('explains when a message cannot be sent, and keeps the chat usable', async () => {
    workspace({
      [SEND]: () =>
        apiError(409, 'turn_in_progress', 'Your mentor is still replying. Wait for that to finish first.'),
    })

    await userEvent.type(await screen.findByLabelText('Message your mentor'), 'Hello')
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText(/still replying/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByText(/still replying/)).not.toBeInTheDocument()
  })

  it('shows a retry button on a failed reply', async () => {
    workspace({
      [MESSAGES]: () =>
        json({
          messages: [
            message('m1', 'user', [{ type: 'markdown', text: 'Hi' }]),
            message(
              'm2',
              'assistant',
              [{ type: 'error', code: 'unavailable', text: "Your mentor couldn't be reached.", retryable: true }],
              { status: 'error' },
            ),
          ],
          next_before: null,
        }),
    })

    expect(await screen.findByText("Your mentor couldn't be reached.")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('records feedback on a reply', async () => {
    let body: unknown
    workspace({
      [MESSAGES]: () =>
        json({
          messages: [message('m1', 'user', [{ type: 'markdown', text: 'Hi' }]), reply],
          next_before: null,
        }),
      'POST /api/v1/messages/m2/feedback': async (request: Request) => {
        body = await request.json()
        return json({ ...reply, feedback: 1 })
      },
    })

    const helpful = await screen.findByRole('button', { name: 'This was helpful' })
    await userEvent.click(helpful)

    await waitFor(() => expect(helpful).toHaveAttribute('aria-pressed', 'true'))
    expect(body).toEqual({ value: 1 })
  })
})

describe('projects', () => {
  it('starts a project in one tap and opens its chat', async () => {
    mockApi({
      'GET /api/v1/users/me': () => json(student),
      'POST /api/v1/projects': () => json({ ...project, title: 'New project' }, 201),
      [MESSAGES]: () => json({ messages: [], next_before: null }),
    })
    const { router } = renderApp('/app/projects')

    await userEvent.click(await screen.findByRole('button', { name: 'Start a new project' }))

    await waitFor(() => expect(router.state.location.pathname).toBe(`/project/${PROJECT_ID}`))
    expect(await screen.findByLabelText('Message your mentor')).toBeInTheDocument()
  })

  it('lists projects with their stage', async () => {
    mockApi({
      'GET /api/v1/users/me': () => json(student),
      'GET /api/v1/projects': () => json([project]),
    })
    renderApp('/app/projects')

    expect(await screen.findByText('Solar phone charger')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Stage 3 of 9' })).toBeInTheDocument()
  })
})
