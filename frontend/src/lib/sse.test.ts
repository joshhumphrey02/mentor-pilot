import { describe, expect, it } from 'vitest'

import { readEvents, type ServerEvent } from './sse'

function streamOf(chunks: string[]): Response {
  const encoder = new TextEncoder()
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
        controller.close()
      },
    }),
  )
}

async function collect(response: Response): Promise<ServerEvent[]> {
  const events: ServerEvent[] = []
  for await (const event of readEvents(response)) events.push(event)
  return events
}

describe('readEvents', () => {
  it('parses named events', async () => {
    const events = await collect(
      streamOf(['event: text_delta\ndata: {"text":"Hi"}\n\nevent: done\ndata: {}\n\n']),
    )

    expect(events).toEqual([
      { event: 'text_delta', data: '{"text":"Hi"}' },
      { event: 'done', data: '{}' },
    ])
  })

  it('reassembles events split across network chunks', async () => {
    const events = await collect(
      streamOf(['event: text_d', 'elta\ndata: {"te', 'xt":"Hi"}\n', '\nevent: done\ndata: {}\n\n']),
    )

    expect(events.map((event) => event.event)).toEqual(['text_delta', 'done'])
    expect(events[0]?.data).toBe('{"text":"Hi"}')
  })

  it('accepts CRLF line endings, even when split between CR and LF', async () => {
    const events = await collect(streamOf(['event: done\r\ndata: {}\r', '\n\r\n']))

    expect(events).toEqual([{ event: 'done', data: '{}' }])
  })

  it('ignores keep-alive comments', async () => {
    const events = await collect(streamOf([': ping\n\n', 'event: done\ndata: {}\n\n']))

    expect(events).toEqual([{ event: 'done', data: '{}' }])
  })

  it('does not split a multi-byte character that straddles two chunks', async () => {
    const bytes = new TextEncoder().encode('event: text_delta\ndata: "é"\n\n')
    const cut = bytes.indexOf(0xc3) + 1 // between the two bytes of "é"
    const response = new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(bytes.slice(0, cut))
          controller.enqueue(bytes.slice(cut))
          controller.close()
        },
      }),
    )

    expect((await collect(response))[0]?.data).toBe('"é"')
  })

  it('drops an unfinished event at the end of the stream', async () => {
    const events = await collect(streamOf(['event: done\ndata: {}\n\nevent: text_delta\ndata: {"t']))

    expect(events).toHaveLength(1)
  })
})
