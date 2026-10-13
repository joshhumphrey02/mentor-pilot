import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiError, json, mockApi, renderApp, student } from '@/test/app'

import { navFor } from '../app-shell/nav'

afterEach(() => vi.unstubAllGlobals())

const at = '2026-10-01T10:00:00Z'
const request = {
  id: 'r1',
  project_id: 'p1',
  project_title: 'Solar charger',
  status: 'matched',
  stage_key: 'design_prototyping',
  help_types: ['hardware_build'],
  description: 'I need help soldering.',
  province: 'Western Cape',
  school_name: 'Langa High',
  snapshot: { title: 'Solar charger', stage: 'Design and Prototyping' },
  learner: { id: 'u1', first_name: 'Thandi' },
  mentor: { id: 'u2', first_name: 'Sipho' },
  created_at: at,
  updated_at: at,
}
const mentor = { ...student, role: 'mentor', full_name: 'Sipho Dlamini' }
const profile = {
  organisation: 'Makerspace',
  bio: '',
  expertise: ['hardware_build'],
  regions: ['Western Cape'],
  availability: 'Saturdays',
  offers: '',
  is_approved: true,
}

describe('navigation by role', () => {
  it('gives each role only the places that mean something to it', () => {
    expect(navFor('student').map((item) => item.label)).toEqual(['Home', 'Projects', 'Mentor', 'Profile'])
    expect(navFor('mentor').map((item) => item.label)).toEqual(['Requests', 'Profile'])
    expect(navFor('admin').map((item) => item.label)).toContain('Admin')
    expect(navFor('student').map((item) => item.label)).not.toContain('Admin')
  })
})

describe('learner and mentor messaging', () => {
  it('shows the request, its status and the thread, and sends a message', async () => {
    let sent: unknown
    mockApi({
      'GET /api/v1/users/me': () => json(student),
      'GET /api/v1/mentor-requests': () => json([request]),
      'GET /api/v1/mentor-requests/r1/messages': () =>
        json([{ id: 'm1', sender: request.mentor, mine: false, text: 'What have you built?', created_at: at }]),
      'POST /api/v1/mentor-requests/r1/messages': async (incoming: Request) => {
        sent = await incoming.json()
        return json({ id: 'm2', sender: request.learner, mine: true, text: 'Just the frame.', created_at: at }, 201)
      },
    })
    renderApp('/app/mentor')

    expect(await screen.findByRole('heading', { name: 'Solar charger' })).toBeInTheDocument()
    expect(screen.getByText('Mentor found')).toBeInTheDocument()
    expect(screen.getByText('Your mentor: Sipho')).toBeInTheDocument()
    expect(await screen.findByText('What have you built?')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Message'), 'Just the frame.')
    await userEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(sent).toEqual({ text: 'Just the frame.' }))
  })

  it('explains why a message with contact details was refused', async () => {
    mockApi({
      'GET /api/v1/users/me': () => json(student),
      'GET /api/v1/mentor-requests': () => json([request]),
      'GET /api/v1/mentor-requests/r1/messages': () => json([]),
      'POST /api/v1/mentor-requests/r1/messages': () =>
        apiError(400, 'contact_details_not_allowed', "Phone numbers can't be shared here."),
    })
    renderApp('/app/mentor')

    await userEvent.type(await screen.findByLabelText('Message'), 'Call me on 082 555 0142')
    await userEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText("Phone numbers can't be shared here.")).toBeInTheDocument()
    expect(screen.getByLabelText('Message')).toHaveValue('Call me on 082 555 0142')
  })
})

describe('mentor dashboard', () => {
  it('lets an approved mentor accept an open request', async () => {
    const accepted = vi.fn(() => json({ ...request, status: 'matched' }))
    mockApi({
      'GET /api/v1/users/me': () => json(mentor),
      'GET /api/v1/mentors/me': () => json(profile),
      'GET /api/v1/mentors/open-requests': () => json([{ ...request, status: 'pending', mentor: null }]),
      'GET /api/v1/mentor-requests': () => json([]),
      'POST /api/v1/mentor-requests/r1/accept': accepted,
    })
    renderApp('/app/mentor')

    const open = within(await screen.findByRole('region', { name: 'Open requests for you' }))
    expect(await open.findByText('Thandi · Langa High · Western Cape')).toBeInTheDocument()
    await userEvent.click(open.getByRole('button', { name: 'Accept this request' }))

    await waitFor(() => expect(accepted).toHaveBeenCalled())
  })

  it('tells an unapproved mentor they are waiting, and shows no requests', async () => {
    const { count } = mockApi({
      'GET /api/v1/users/me': () => json(mentor),
      'GET /api/v1/mentors/me': () => json({ ...profile, is_approved: false }),
      'GET /api/v1/mentor-requests': () => json([]),
    })
    renderApp('/app/mentor')

    expect(await screen.findByText(/waiting for approval/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Open requests for you' })).not.toBeInTheDocument()
    expect(count('GET /api/v1/mentors/open-requests')).toBe(0)
  })

  it('sends a mentor who opens the home page to their requests', async () => {
    mockApi({
      'GET /api/v1/users/me': () => json(mentor),
      'GET /api/v1/mentors/me': () => json(profile),
      'GET /api/v1/mentors/open-requests': () => json([]),
      'GET /api/v1/mentor-requests': () => json([]),
    })
    const { router } = renderApp('/app')

    await waitFor(() => expect(router.state.location.pathname).toBe('/app/mentor'))
  })
})

describe('admin', () => {
  it('keeps non-admins out', async () => {
    mockApi({ 'GET /api/v1/users/me': () => json(student) })
    const { router } = renderApp('/app/admin')

    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
  })

  it('shows usage with unknown costs marked as unknown, and approves a mentor', async () => {
    const approve = vi.fn(() => json({}))
    mockApi({
      'GET /api/v1/users/me': () => json({ ...student, role: 'admin' }),
      'GET /api/v1/admin/usage': () =>
        json([
          { key: 'a', label: 'acme / big', calls: 2, input_tokens: 1200, output_tokens: 300, cost_usd: '0.750000' },
          { key: 'b', label: 'acme / small', calls: 1, input_tokens: 100, output_tokens: 50, cost_usd: null },
        ]),
      'GET /api/v1/admin/mentors': () =>
        json([
          {
            user: { id: 'u2', email: 'sipho@example.com', full_name: 'Sipho Dlamini', role: 'mentor', is_active: true, is_verified: true, created_at: at, last_login_at: null },
            profile: { ...profile, is_approved: false },
          },
        ]),
      'POST /api/v1/admin/mentors/u2/approval': approve,
    })
    renderApp('/app/admin')

    const row = await screen.findByRole('row', { name: /acme \/ small/ })
    expect(within(row).getByText('unknown')).toBeInTheDocument()
    // Once in the row and once in the total above the table.
    expect(screen.getAllByText('$0.75')).toHaveLength(2)

    await userEvent.click(screen.getByRole('tab', { name: 'Mentors' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(approve).toHaveBeenCalled())
  })
})
