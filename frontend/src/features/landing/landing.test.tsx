import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { json, mockApi, renderApp, student } from '@/test/app'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('landing page', () => {
  it('pitches the product and offers sign-up and log-in to visitors', async () => {
    mockApi()
    renderApp('/')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Your idea, expo-ready.' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Start your project/ })[0]).toHaveAttribute('href', '/register')
    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: /Become a mentor/ })).toHaveAttribute('href', '/register-mentor')
  })

  it('takes a signed-in learner to their workspace instead', async () => {
    mockApi({ 'GET /api/v1/users/me': () => json(student) })
    renderApp('/')

    expect((await screen.findAllByRole('link', { name: /Open your workspace/ }))[0]).toHaveAttribute('href', '/app')
    expect(screen.queryByRole('link', { name: 'Log in' })).not.toBeInTheDocument()
  })

  it('includes a working breadboard demo that needs no account', async () => {
    const { count } = mockApi()
    renderApp('/')

    await userEvent.click(await screen.findByRole('radio', { name: "Don't" }, { timeout: 5000 }))

    expect(screen.getByText(/Both LED legs in one column/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /red LED/ }))
    expect(await screen.findByRole('dialog')).toHaveTextContent('light-emitting diode')
    expect(count('GET /api/v1/media/component-photo/led')).toBe(0)
  })

  it('shows all nine stages as photo cards, marking where a human mentor joins', async () => {
    mockApi()
    renderApp('/')

    const stages = within(await screen.findByRole('list', { name: 'The nine stages of a project' }))
    expect(stages.getAllByRole('listitem')).toHaveLength(9)
    expect(stages.getByRole('heading', { name: 'Problem Discovery' })).toBeInTheDocument()
    const handoff = stages.getByRole('heading', { name: 'Design and Prototyping' }).closest('li')
    expect(handoff).toHaveTextContent('Stage 6')
    expect(handoff).toHaveTextContent('A human mentor joins')
  })

  it('stops the hero slideshow once a visitor picks a photo', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockApi()
    renderApp('/')
    const first = await screen.findByRole('button', { name: 'Show photo 1 of 4' })
    expect(first).toHaveAttribute('aria-current', 'true')

    await act(() => vi.advanceTimersByTimeAsync(5600))
    expect(screen.getByRole('button', { name: 'Show photo 2 of 4' })).toHaveAttribute('aria-current', 'true')

    await userEvent.click(screen.getByRole('button', { name: 'Show photo 4 of 4' }))
    await act(() => vi.advanceTimersByTimeAsync(12000))
    expect(screen.getByRole('button', { name: 'Show photo 4 of 4' })).toHaveAttribute('aria-current', 'true')
  })

  it('credits the photographers', async () => {
    mockApi()
    renderApp('/')

    expect(await screen.findByText(/Photos by .*ThisisEngineering.* on/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Unsplash' })).toHaveAttribute('href', 'https://unsplash.com')
  })
})
