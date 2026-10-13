/** An error response from the API, with the stable `code` the UI can switch on. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

const FALLBACK = 'Something went wrong. Please try again.'

function toApiError(body: unknown, status: number): ApiError {
  if (body && typeof body === 'object') {
    const { detail, code } = body as { detail?: unknown; code?: unknown }
    if (typeof detail === 'string') {
      return new ApiError(detail, typeof code === 'string' ? code : 'error', status)
    }
    // FastAPI validation errors (422) carry a list; forms validate first, so
    // reaching this means the client and server rules have drifted.
    if (Array.isArray(detail)) {
      return new ApiError('Please check what you entered and try again.', 'validation', status)
    }
  }
  return new ApiError(FALLBACK, 'error', status)
}

/** Turns an openapi-fetch result into its data, or throws an ApiError. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (!result.response.ok) throw toApiError(result.error, result.response.status)
  return result.data as T
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) return "We couldn't reach the server. Check your connection."
  return FALLBACK
}

export function errorCode(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null
}
