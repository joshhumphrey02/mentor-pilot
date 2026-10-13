import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests drive the real app in a phone-sized browser.
 *
 * They start both dev servers with the fake AI provider, so they need no API
 * key and spend nothing. Before the first run: `make migrate && make seed`
 * (for the demo learner) and `npx playwright install chromium`.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'mobile',
      // The spec's target: 390x844, a current mid-size phone, with touch.
      use: {
        ...devices['Pixel 7'],
        viewport: { width: 390, height: 844 },
      },
    },
  ],
  webServer: {
    command: 'make -C .. dev',
    url: 'http://localhost:5173/api/v1/health',
    reuseExistingServer: true,
    timeout: 60_000,
    env: { AI_PROVIDER: 'fake', AI_MODEL: 'fake', RATE_LIMIT_ENABLED: 'false' },
  },
})
