import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiError, json, mockApi, renderApp, student } from '@/test/app'

import { safeRedirect } from './guards'

afterEach(() => vi.unstubAllGlobals())

describe('login', () => {
  it('validates before calling the server', async () => {
    const { count } = mockApi()
    renderApp('/login')

    await userEvent.click(await screen.findByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Enter your email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(count('POST /api/v1/auth/login')).toBe(0)
  })

  it('signs in and opens the app', async () => {
    mockApi({ 'POST /api/v1/auth/login': () => json(student) })
    const { router } = renderApp('/login')

    await userEvent.type(await screen.findByLabelText('Email'), 'thandi@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct horse battery')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
    expect(await screen.findByRole('heading', { name: /Thandi/ })).toBeInTheDocument()
  })

  it('sends a learner who has not onboarded to onboarding', async () => {
    mockApi({ 'POST /api/v1/auth/login': () => json({ ...student, is_onboarded: false }) })
    const { router } = renderApp('/login')

    await userEvent.type(await screen.findByLabelText('Email'), 'thandi@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct horse battery')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/onboarding'))
  })

  it('offers to resend the link when the email is not confirmed yet', async () => {
    const { count } = mockApi({
      'POST /api/v1/auth/login': () =>
        apiError(403, 'email_not_verified', 'Please confirm your email address first.'),
      'POST /api/v1/auth/resend-verification': () => json({ message: 'ok' }, 202),
    })
    renderApp('/login')

    await userEvent.type(await screen.findByLabelText('Email'), 'thandi@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct horse battery')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Send the link again' }))

    expect(await screen.findByText("We've sent a new link.")).toBeInTheDocument()
    expect(count('POST /api/v1/auth/resend-verification')).toBe(1)
  })
})

describe('route guards', () => {
  it('sends visitors to login and remembers where they were going', async () => {
    mockApi()
    const { router } = renderApp('/app/profile')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/app/profile' })
  })

  it('keeps signed-in users out of the login page', async () => {
    mockApi({ 'GET /api/v1/users/me': () => json(student) })
    const { router } = renderApp('/login')

    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
  })

  it('only follows redirects that stay inside the app', () => {
    expect(safeRedirect('/app/projects')).toBe('/app/projects')
    expect(safeRedirect('https://evil.example')).toBeUndefined()
    expect(safeRedirect('//evil.example')).toBeUndefined()
    expect(safeRedirect('/\\evil.example')).toBeUndefined()
    expect(safeRedirect(undefined)).toBeUndefined()
  })
})

describe('register', () => {
  it('requires the privacy notice to be accepted', async () => {
    const { count } = mockApi()
    renderApp('/register')

    await userEvent.type(await screen.findByLabelText('Your name'), 'Thandi')
    await userEvent.type(screen.getByLabelText('Email'), 'thandi@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct horse battery')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(
      await screen.findByText('Please accept the privacy notice to continue.'),
    ).toBeInTheDocument()
    expect(count('POST /api/v1/auth/register')).toBe(0)
  })

  it('shows the check-your-inbox screen after signing up', async () => {
    mockApi({ 'POST /api/v1/auth/register': () => json({ message: 'ok' }, 202) })
    renderApp('/register')

    await userEvent.type(await screen.findByLabelText('Your name'), 'Thandi')
    await userEvent.type(screen.getByLabelText('Email'), 'thandi@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct horse battery')
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('heading', { name: 'Check your inbox' })).toBeInTheDocument()
    expect(screen.getByText('thandi@example.com')).toBeInTheDocument()
  })
})
