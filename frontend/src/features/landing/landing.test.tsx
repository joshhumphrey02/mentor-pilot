import { act, screen } from '@testing-library/react'
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
      await screen.findByRole('heading', { level: 1, name: /From an idea on paper to a project on the expo floor/ }),
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

  it('walks through the pathway by itself until a stage is picked', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockApi()
    renderApp('/')
    await screen.findByText('Stage 1 of 9')

    await act(() => vi.advanceTimersByTimeAsync(2700))
    expect(screen.getByText('Stage 2 of 9')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Stage 6: Design and Prototyping' }))
    expect(screen.getByText('A human mentor joins here')).toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(6000))
    expect(screen.getByText('Stage 6 of 9'), 'picking a stage stops the autoplay').toBeInTheDocument()
  })
})
