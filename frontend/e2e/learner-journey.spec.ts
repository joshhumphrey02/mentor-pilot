import { expect, test } from '@playwright/test'

// The demo learner created by `make seed`.
const EMAIL = 'student@demo.example.com'
const PASSWORD = 'mentorpilot-demo'

test('a learner logs in, starts a project and explores a breadboard on a phone', async ({ page }) => {
  // The public landing page, with the demo that needs no account.
  await page.goto('/')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Your idea, expo-ready.' }),
  ).toBeVisible()
  await expect(page).toHaveTitle('Mentor Pilot')

  // Nothing may be wider than the phone.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.visualViewport!.width,
  )
  expect(overflow, 'no horizontal scrolling on the landing page').toBeLessThanOrEqual(0)

  // Log in.
  await page.getByRole('link', { name: 'Log in' }).click()
  await page.getByLabel('Email').fill(EMAIL)
  // By role: the show/hide button beside it is also labelled with "password".
  await page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Log in' }).click()

  // The dashboard, with the bottom tab bar a thumb can reach.
  await expect(page.getByRole('heading', { level: 1, name: /Good (morning|afternoon|evening)/ })).toBeVisible()
  const tabs = page.getByRole('navigation', { name: 'Main' }).last()
  await expect(tabs.getByRole('link', { name: 'Projects' })).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Your projects' })).toBeVisible()
  const dashboardOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.visualViewport!.width,
  )
  expect(dashboardOverflow, 'no horizontal scrolling on the dashboard').toBeLessThanOrEqual(0)
  await page.screenshot({ path: 'test-results/shots/dashboard.png' })

  // Start a new project: one tap, straight into the chat.
  await tabs.getByRole('link', { name: 'Projects' }).click()
  await page.getByRole('button', { name: 'Start a new project' }).click()
  await expect(page).toHaveURL(/\/project\//)
  await expect(page.getByText(/Stage 1 of 9 · Problem Discovery/)).toBeVisible()
  await expect(page.getByRole('heading', { name: /I'm your mentor/ })).toBeVisible()

  // Ask the signature question.
  const input = page.getByLabel('Message your mentor')
  await input.fill('How do I connect an LED on a breadboard?')
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.getByText('How do I connect an LED on a breadboard?')).toBeVisible()

  // An interactive breadboard arrives, streamed into the reply.
  const board = page.getByRole('region', { name: 'Lighting an LED' })
  await expect(board).toBeVisible()
  await expect(board.getByRole('button', { name: /red LED\. anode in D10, cathode in D11/ })).toBeVisible()

  await page.screenshot({ path: 'test-results/shots/breadboard.png', fullPage: false })

  // Do / Don't: the common mistake, explained.
  await board.getByRole('radio', { name: "Don't" }).click()
  await expect(board.getByText("Don't: Both LED legs in one column")).toBeVisible()
  await board.scrollIntoViewIfNeeded()
  await page.screenshot({ path: 'test-results/shots/dont.png' })
  await board.getByRole('radio', { name: 'Do', exact: true }).click()

  // Reveal inside.
  await board.getByRole('button', { name: 'Reveal inside' }).click()
  await expect(board.getByText(/each column of five holes sits on one metal strip/)).toBeVisible()
  await board.getByRole('button', { name: 'Reveal inside' }).click()

  // Step through the build.
  await board.getByRole('button', { name: 'Step through' }).click()
  await expect(board.getByText('Step 1 of 5')).toBeVisible()
  await board.getByRole('button', { name: 'Next' }).click()
  await expect(board.getByText('Step 2 of 5')).toBeVisible()

  // Tap a part to learn about it.
  await board.getByRole('button', { name: /Resistor/ }).click()
  await expect(page.getByRole('dialog')).toContainText('Limits how much current flows')
  await page.keyboard.press('Escape')

  // The reply ended with suggested replies, as tappable chips above the input.
  await expect(page.getByRole('list', { name: 'Suggested replies' })).toBeVisible()

  // The conversation survives a refresh.
  await page.reload()
  await expect(page.getByRole('region', { name: 'Lighting an LED' })).toBeVisible()
  await expect(page.getByText('How do I connect an LED on a breadboard?')).toBeVisible()

  // Still nothing wider than the phone, with the breadboard on screen.
  const chatOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.visualViewport!.width,
  )
  expect(chatOverflow, 'no horizontal scrolling in the workspace').toBeLessThanOrEqual(0)
})
