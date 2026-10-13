import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiError, json, mockApi, student } from '@/test/app'

import { api } from './client'

describe('api client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.cookie = 'mp_csrf=; max-age=0'
  })

  it('sends the CSRF token on writes but not on reads', async () => {
    document.cookie = 'mp_csrf=token-123'
    const { calls } = mockApi({
      'GET /api/v1/users/me': () => json(student),
      'PATCH /api/v1/users/me': () => json(student),
    })

    await api.GET('/api/v1/users/me')
    await api.PATCH('/api/v1/users/me', { body: { full_name: 'Thandi' } })

    expect(calls[0]?.headers.get('X-CSRF-Token')).toBeNull()
    expect(calls[1]?.headers.get('X-CSRF-Token')).toBe('token-123')
  })

  it('retries once when the server clears cookies it no longer recognises', async () => {
    let stale = true
    const { calls } = mockApi({
      'POST /api/v1/auth/login': () => {
        if (!stale) return json(student)
        stale = false
        return apiError(403, 'csrf_failed')
      },
    })

    const { response } = await api.POST('/api/v1/auth/login', {
      body: { email: student.email, password: 'correct horse battery' },
    })

    expect(response.status).toBe(200)
    expect(calls).toHaveLength(2)
    expect(await calls[1]?.json()).toEqual({ email: student.email, password: 'correct horse battery' })
  })

  it('refreshes an expired session once and retries the request with its body', async () => {
    let expired = true
    const { calls, count } = mockApi({
      'PATCH /api/v1/users/me': () => (expired ? apiError(401, 'not_authenticated') : json(student)),
      'POST /api/v1/auth/refresh': () => {
        expired = false
        return json(student)
      },
    })

    const { data, response } = await api.PATCH('/api/v1/users/me', { body: { full_name: 'Thandi' } })

    expect(response.status).toBe(200)
    expect(data?.email).toBe(student.email)
    expect(count('POST /api/v1/auth/refresh')).toBe(1)
    expect(await calls.at(-1)?.json()).toEqual({ full_name: 'Thandi' })
  })

  it('shares one refresh between requests that expire together', async () => {
    let expired = true
    const { count } = mockApi({
      'GET /api/v1/users/me': () => (expired ? apiError(401, 'not_authenticated') : json(student)),
      'POST /api/v1/auth/refresh': async () => {
        await new Promise((resolve) => setTimeout(resolve, 10))
        expired = false
        return json(student)
      },
    })

    const results = await Promise.all([api.GET('/api/v1/users/me'), api.GET('/api/v1/users/me')])

    expect(results.map((result) => result.response.status)).toEqual([200, 200])
    expect(count('POST /api/v1/auth/refresh')).toBe(1)
  })

  it('gives up when the session cannot be refreshed', async () => {
    const { count } = mockApi({
      'POST /api/v1/auth/refresh': () => apiError(401, 'invalid_session'),
    })

    const { response } = await api.GET('/api/v1/users/me')

    expect(response.status).toBe(401)
    expect(count('GET /api/v1/users/me')).toBe(1)
  })

  it('does not try to refresh after a failed login', async () => {
    const { count } = mockApi({
      'POST /api/v1/auth/login': () => apiError(401, 'invalid_credentials'),
    })

    await api.POST('/api/v1/auth/login', { body: { email: 'a@b.co', password: 'x' } })

    expect(count('POST /api/v1/auth/refresh')).toBe(0)
  })
})
