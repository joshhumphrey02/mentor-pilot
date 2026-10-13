import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { json, mockApi, renderApp, student } from '@/test/app'

import { ageFrom, isMinor } from './options'

afterEach(() => vi.unstubAllGlobals())

const newLearner = { ...student, is_onboarded: false }

function yearsAgo(years: number) {
  const date = new Date()
  date.setFullYear(date.getFullYear() - years)
  date.setDate(1)
  return date.toISOString().slice(0, 10)
}

describe('age rules', () => {
  it('counts birthdays, not calendar years', () => {
    expect(ageFrom('2010-06-15', new Date(2028, 5, 14))).toBe(17)
    expect(ageFrom('2010-06-15', new Date(2028, 5, 15))).toBe(18)
  })

  it('treats an unparseable date as not a minor', () => {
    expect(isMinor('')).toBe(false)
  })
})

describe('onboarding', () => {
  it('asks under-18s for a guardian, and blocks the step until it is filled in', async () => {
    mockApi({ 'GET /api/v1/users/me': () => json(newLearner) })
    renderApp('/onboarding')

    const dob = await screen.findByLabelText('Date of birth')
    expect(screen.queryByLabelText('Their email address')).not.toBeInTheDocument()

    await userEvent.type(dob, yearsAgo(15))
    expect(await screen.findByLabelText('Their email address')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(
      await screen.findByText('Enter the email of a parent, guardian or teacher.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Step 1 of 4')).toBeInTheDocument()
  })

  it('does not ask adults for a guardian', async () => {
    mockApi({ 'GET /api/v1/users/me': () => json(newLearner) })
    renderApp('/onboarding')

    await userEvent.type(await screen.findByLabelText('Date of birth'), yearsAgo(20))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText('Step 2 of 4')).toBeInTheDocument()
    expect(screen.queryByLabelText('Their email address')).not.toBeInTheDocument()
  })

  it('walks through every step and submits the profile', async () => {
    let submitted: Record<string, unknown> | undefined
    mockApi({
      'GET /api/v1/users/me': () => json(newLearner),
      'GET /api/v1/schools': () =>
        json([
          { id: 'school-1', name: 'Langa High School', province: 'Western Cape', town: 'Cape Town', is_verified: true },
        ]),
      'POST /api/v1/users/me/onboarding': async (request) => {
        submitted = (await request.json()) as Record<string, unknown>
        return json(student)
      },
    })
    const { router } = renderApp('/onboarding')

    await userEvent.type(await screen.findByLabelText('Date of birth'), yearsAgo(15))
    await userEvent.type(await screen.findByLabelText('Their email address'), 'parent@example.com')
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    await userEvent.type(await screen.findByLabelText('Your school'), 'Langa')
    await userEvent.click(await screen.findByRole('button', { name: /Langa High School/ }))
    await userEvent.selectOptions(screen.getByLabelText('Grade'), '10')
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Robotics' }))
    await userEvent.click(screen.getByRole('button', { name: 'Energy' }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    await userEvent.click(await screen.findByRole('radio', { name: /Let me try/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Meet your mentor' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
    expect(submitted).toMatchObject({
      full_name: 'Thandi Mokoena',
      school_id: 'school-1',
      new_school: null,
      grade: '10',
      province: 'Western Cape',
      interests: ['robotics', 'energy'],
      learning_style: 'hands_on',
      guardian_consent: true,
      guardian_email: 'parent@example.com',
    })
  })

  it('needs at least one interest', async () => {
    mockApi({ 'GET /api/v1/users/me': () => json(newLearner) })
    renderApp('/onboarding')

    await userEvent.type(await screen.findByLabelText('Date of birth'), yearsAgo(20))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await userEvent.click(await screen.findByRole('button', { name: "I'm not at a school" }))
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await screen.findByText('Step 3 of 4')
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText('Pick at least one.')).toBeInTheDocument()
  })
})
