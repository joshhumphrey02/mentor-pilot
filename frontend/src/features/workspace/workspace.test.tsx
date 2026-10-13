import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { json, mockApi, renderApp, student } from '@/test/app'

import { toChart, toNumber } from './data-chart'

afterEach(() => vi.unstubAllGlobals())

const at = '2026-10-01T10:00:00Z'
const conversation = { id: 'c1', project_id: 'p1', title: '', last_message_at: at, created_at: at }
const project = {
  id: 'p1',
  title: 'Tap water',
  current_stage: 'problem_discovery',
  status: 'active',
  idea: null,
  last_activity_at: at,
  created_at: at,
  latest_conversation: conversation,
}
const stages = [
  {
    key: 'problem_discovery',
    position: 1,
    title: 'Problem Discovery',
    goal: 'Find a real problem.',
    status: 'active',
    handoff: false,
    checklist: [{ key: 'observations', label: 'List three problems', done: false, note: '' }],
  },
]
const diagramReply = {
  id: 'm2',
  conversation_id: 'c1',
  role: 'assistant',
  status: 'complete',
  feedback: null,
  created_at: at,
  blocks: [
    { type: 'markdown', text: 'Here it is.' },
    {
      type: 'bom_table',
      title: 'Bill of materials',
      total_zar: 5,
      items: [{ name: 'LED', quantity: 2, unit_price_zar: 2.5, where_to_get: '', substitute: '' }],
    },
  ],
}

function open(handlers = {}) {
  const api = mockApi({
    'GET /api/v1/users/me': () => json(student),
    'GET /api/v1/projects/p1': () => json(project),
    'GET /api/v1/projects/p1/stages': () => json(stages),
    'GET /api/v1/conversations/c1/messages': () => json({ messages: [], next_before: null }),
    'GET /api/v1/projects/p1/logbook': () => json([]),
    'GET /api/v1/projects/p1/pins': () => json([]),
    'GET /api/v1/projects/p1/datasets': () => json([]),
    ...handlers,
  })
  return { ...api, ...renderApp('/project/p1') }
}

/** The desktop side panel (the phone version is the same component in a sheet). */
async function panel() {
  return within(await screen.findByRole('complementary', { name: 'Project tools' }))
}

describe('turning a table into a chart', () => {
  it('reads numbers, including a decimal comma', () => {
    expect(toNumber('3.5')).toBe(3.5)
    expect(toNumber(' 3,5 ')).toBe(3.5)
    expect(toNumber('')).toBeNull()
    expect(toNumber('about 3')).toBeNull()
  })

  it('plots numeric columns against the first column', () => {
    const chart = toChart('Drips', ['Minute', 'ml', 'Notes'], [
      ['1', '40', 'steady'],
      ['2', '38,5', ''],
      ['3', '', 'missed it'],
    ])

    expect(chart?.chart_type).toBe('line')
    expect(chart?.x_label).toBe('Minute')
    expect(chart?.series).toEqual([{ name: 'ml', points: [{ x: 1, y: 40 }, { x: 2, y: 38.5 }] }])
  })

  it('uses bars when the first column is categories', () => {
    const chart = toChart('Height', ['Fertiliser', 'cm'], [['None', '4'], ['Compost', '9']])

    expect(chart?.chart_type).toBe('bar')
    expect(chart?.series[0]?.points).toEqual([{ x: 'None', y: 4 }, { x: 'Compost', y: 9 }])
  })

  it('has nothing to plot until there are numbers', () => {
    expect(toChart('Empty', ['Trial', 'ml'], [['1', ''], ['2', '']])).toBeNull()
  })
})

describe('project tools', () => {
  it('shows the current stage checklist first', async () => {
    open()
    const tools = await panel()

    expect(await tools.findByText('Stage 1: Problem Discovery')).toBeInTheDocument()
    expect(tools.getByRole('tab', { name: 'Checklist' })).toHaveAttribute('aria-selected', 'true')
    expect(tools.getByRole('checkbox', { name: /List three problems/ })).toBeInTheDocument()
    expect(tools.getByRole('link', { name: /Download project summary/ })).toHaveAttribute(
      'href',
      '/api/v1/projects/p1/export.pdf',
    )
  })

  it('adds a logbook entry', async () => {
    let saved: unknown
    open({
      'POST /api/v1/projects/p1/logbook': async (request: Request) => {
        saved = await request.json()
        return json({ id: 'l1', text: 'Counted drips', stage_key: 'problem_discovery', created_at: at, updated_at: at }, 201)
      },
    })
    const tools = await panel()

    await userEvent.click(tools.getByRole('tab', { name: 'Logbook' }))
    expect(await tools.findByText(/Judges read logbooks/)).toBeInTheDocument()
    await userEvent.type(tools.getByLabelText('What did you do today?'), 'Counted drips')
    await userEvent.click(tools.getByRole('button', { name: 'Add to logbook' }))

    await waitFor(() => expect(saved).toEqual({ text: 'Counted drips' }))
    await waitFor(() => expect(tools.getByLabelText('What did you do today?')).toHaveValue(''))
  })

  it('lets the learner enter data and save it', async () => {
    let saved: { rows?: string[][] } | undefined
    open({
      'POST /api/v1/projects/p1/datasets': async (request: Request) => {
        saved = (await request.json()) as { rows: string[][] }
        return json({ id: 'd1', title: 'My results', columns: ['Trial', 'Measurement'], rows: saved.rows, updated_at: at }, 201)
      },
    })
    const tools = await panel()

    await userEvent.click(tools.getByRole('tab', { name: 'Data' }))
    expect(await tools.findByText(/Type numbers into a column/)).toBeInTheDocument()
    await userEvent.type(tools.getByLabelText('Measurement, row 1'), '40')
    await userEvent.type(tools.getByLabelText('Measurement, row 2'), '38')
    await userEvent.click(tools.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(saved?.rows).toEqual([['1', '40'], ['2', '38'], ['3', '']]))
    expect(tools.queryByText(/Type numbers into a column/)).not.toBeInTheDocument()
  })

  it('saves a block from a reply and lists it under Saved', async () => {
    let pinned: unknown
    open({
      'GET /api/v1/conversations/c1/messages': () =>
        json({
          messages: [
            { ...diagramReply, id: 'm1', role: 'user', blocks: [{ type: 'markdown', text: 'What do I need?' }] },
            diagramReply,
          ],
          next_before: null,
        }),
      'POST /api/v1/projects/p1/pins': async (request: Request) => {
        pinned = await request.json()
        return json({ id: 'pin1', title: 'Bill of materials', block: diagramReply.blocks[1], message_id: 'm2', created_at: at }, 201)
      },
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Saved to your project')).toBeInTheDocument()
    expect(pinned).toEqual({ message_id: 'm2', block_index: 1 })
  })
})

describe('sending a photo', () => {
  it('uploads the photo, shows a preview and sends its id with the message', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:preview')
    URL.revokeObjectURL = vi.fn()
    let sent: unknown
    open({
      'POST /api/v1/projects/p1/attachments': () =>
        json({ id: 'a1', filename: 'circuit.png', content_type: 'image/png', size: 10 }, 201),
      'POST /api/v1/conversations/c1/messages': async (request: Request) => {
        sent = await request.json()
        return new Response('', { headers: { 'content-type': 'text/event-stream' } })
      },
    })
    await screen.findByLabelText('Message your mentor')
    const picker = document.querySelector<HTMLInputElement>('input[type="file"]')!

    await userEvent.upload(picker, new File(['x'], 'circuit.png', { type: 'image/png' }))
    expect(await screen.findByRole('img', { name: 'Ready to send' })).toBeInTheDocument()
    const send = screen.getByRole('button', { name: 'Send message' })
    await waitFor(() => expect(send).toBeEnabled())
    await userEvent.click(send)

    await waitFor(() =>
      expect(sent).toEqual({ text: 'Here is a photo. What do you think?', attachment_ids: ['a1'] }),
    )
  })
})
