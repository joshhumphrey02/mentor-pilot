export interface ServerEvent {
  event: string
  data: string
}

/**
 * Reads a Server-Sent Events response body as it arrives.
 *
 * `EventSource` cannot be used here: it only does GET and cannot send the CSRF
 * header, so the stream is read from a fetch response instead.
 */
export async function* readEvents(response: Response): AsyncGenerator<ServerEvent> {
  if (!response.body) return
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''

  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      // Network chunks do not line up with events, so split on the blank
      // line that ends each one and keep any unfinished tail for next time.
      buffer = (buffer + value).replace(/\r\n?/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const parsed = parseEvent(buffer.slice(0, boundary))
        if (parsed) yield parsed
        buffer = buffer.slice(boundary + 2)
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function parseEvent(raw: string): ServerEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of raw.split('\n')) {
    // Lines starting with ":" are comments; servers send them as keep-alive pings.
    if (line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  return data.length > 0 ? { event, data: data.join('\n') } : null
}
