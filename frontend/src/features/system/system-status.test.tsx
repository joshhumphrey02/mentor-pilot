import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SystemStatus } from './system-status'

function renderStatus() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <SystemStatus />
    </QueryClientProvider>,
  )
}

function mockHealth(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => Response.json(body, { status })),
  )
}

describe('SystemStatus', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows online when the API and database are healthy', async () => {
    mockHealth(200, { status: 'ok', database: 'ok', environment: 'test', version: '0.1.0' })
    renderStatus()

    expect(await screen.findByText('Mentor is online')).toBeInTheDocument()
  })

  it('shows trouble when the API answers but the database is down', async () => {
    mockHealth(503, {
      status: 'degraded',
      database: 'unavailable',
      environment: 'test',
      version: '0.1.0',
    })
    renderStatus()

    expect(await screen.findByText('Mentor is having trouble')).toBeInTheDocument()
  })

  it('shows unreachable when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderStatus()

    expect(await screen.findByText("Can't reach the mentor")).toBeInTheDocument()
  })
})
