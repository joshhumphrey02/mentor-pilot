import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { openStream } from '@/lib/api/client'
import { ApiError, errorMessage } from '@/lib/api/errors'
import { readEvents } from '@/lib/sse'

import {
  type Block,
  type Conversation,
  fetchMessage,
  type Message,
  messagesQueryOptions,
  type StreamEvents,
} from './api'

/** A block as it is being received: finished, still filling with text, or not yet arrived. */
export type DraftBlock =
  | { state: 'done'; block: Block }
  | { state: 'writing'; text: string }
  | { state: 'pending'; kind: string }

export interface PendingTurn {
  /** Shown immediately, before the server has confirmed the message. */
  userText: string | null
  blocks: DraftBlock[]
  toolStatus: string | null
  /** Known once the server has started the turn. Becomes the saved message's id. */
  assistantId: string | null
}

const POLL_INTERVAL_MS = 1500
const POLL_LIMIT = 120

interface UseChatOptions {
  conversationId: string
  onConversationChange?: (conversation: Conversation) => void
  /** Called when a reply has been saved, whatever its outcome. */
  onTurnEnd?: () => void
}

export function useChat({ conversationId, onConversationChange, onTurnEnd }: UseChatOptions) {
  const queryClient = useQueryClient()
  const messagesKey = messagesQueryOptions(conversationId).queryKey
  const messages = useQuery(messagesQueryOptions(conversationId))
  const [pending, setPending] = useState<PendingTurn | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Tokens arrive far faster than the screen refreshes. They are collected
  // here and painted once per frame, so a long answer does not re-render the
  // message list hundreds of times a second.
  const draft = useRef<PendingTurn | null>(null)
  const frame = useRef<number | null>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      if (frame.current !== null) cancelAnimationFrame(frame.current)
    }
  }, [])

  const paint = useCallback(() => {
    if (frame.current !== null) return
    frame.current = requestAnimationFrame(() => {
      frame.current = null
      if (alive.current && draft.current) {
        setPending({ ...draft.current, blocks: [...draft.current.blocks] })
      }
    })
  }, [])

  const appendMessage = useCallback(
    (message: Message) =>
      queryClient.setQueryData(messagesKey, (current) => [
        ...(current ?? []).filter((existing) => existing.id !== message.id),
        message,
      ]),
    [queryClient, messagesKey],
  )

  const finish = useCallback(() => {
    draft.current = null
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current)
      frame.current = null
    }
    if (alive.current) setPending(null)
  }, [])

  /** After a dropped connection: the reply is still being written server-side. */
  const recover = useCallback(
    async (assistantId: string) => {
      for (let attempt = 0; attempt < POLL_LIMIT && alive.current; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
        try {
          const message = await fetchMessage(assistantId)
          if (message.status !== 'streaming') {
            appendMessage(message)
            return
          }
        } catch {
          // Still offline; keep trying until the limit.
        }
      }
      await queryClient.invalidateQueries({ queryKey: messagesKey })
    },
    [appendMessage, queryClient, messagesKey],
  )

  const run = useCallback(
    async (path: string, body: unknown, userText: string | null) => {
      if (draft.current) return
      setError(null)
      draft.current = { userText, blocks: [], toolStatus: null, assistantId: null }
      setPending(draft.current)
      let assistantId: string | null = null
      let finished = false

      const handle = <Name extends keyof StreamEvents>(name: Name, data: StreamEvents[Name]) => {
        const turn = draft.current
        if (!turn) return
        switch (name) {
          case 'message_start': {
            const event = data as StreamEvents['message_start']
            assistantId = event.assistant_message_id
            turn.assistantId = assistantId
            if (event.user_message) appendMessage(event.user_message)
            turn.userText = null
            break
          }
          case 'block_start': {
            const event = data as StreamEvents['block_start']
            turn.blocks[event.index] =
              event.type === 'markdown'
                ? { state: 'writing', text: '' }
                : { state: 'pending', kind: event.type }
            turn.toolStatus = null
            break
          }
          case 'text_delta': {
            const event = data as StreamEvents['text_delta']
            const block = turn.blocks[event.index]
            turn.blocks[event.index] = {
              state: 'writing',
              text: (block?.state === 'writing' ? block.text : '') + event.text,
            }
            break
          }
          case 'block_complete': {
            const event = data as StreamEvents['block_complete']
            turn.blocks[event.index] = { state: 'done', block: event.block }
            break
          }
          case 'tool_status':
            turn.toolStatus = (data as StreamEvents['tool_status']).text
            break
          case 'done':
            // The saved message is the source of truth: it replaces the draft.
            appendMessage((data as StreamEvents['done']).message)
            finished = true
            finish()
            onTurnEnd?.()
            return
          case 'conversation':
            onConversationChange?.((data as StreamEvents['conversation']).conversation)
            return
          default:
            return
        }
        paint()
      }

      try {
        const response = await openStream(path, body)
        if (!response.ok) {
          const problem = (await response.json().catch(() => null)) as {
            detail?: unknown
            code?: unknown
          } | null
          throw new ApiError(
            typeof problem?.detail === 'string' ? problem.detail : 'Your message could not be sent.',
            typeof problem?.code === 'string' ? problem.code : 'error',
            response.status,
          )
        }
        for await (const event of readEvents(response)) {
          handle(event.event as keyof StreamEvents, JSON.parse(event.data) as never)
        }
        if (!finished) throw new TypeError('stream ended early')
      } catch (caught) {
        if (finished) return
        if (assistantId) {
          // The turn started, so the reply will be saved. Wait for it.
          if (draft.current) {
            draft.current.toolStatus = 'Reconnecting…'
            paint()
          }
          await recover(assistantId)
          onTurnEnd?.()
        } else if (alive.current) {
          setError(errorMessage(caught))
        }
        finish()
      }
    },
    [appendMessage, finish, onConversationChange, onTurnEnd, paint, recover],
  )

  const send = useCallback(
    (text: string, attachmentIds: string[] = []) => {
      const trimmed = text.trim()
      if (!trimmed) return
      void run(
        `/api/v1/conversations/${conversationId}/messages`,
        { text: trimmed, attachment_ids: attachmentIds },
        trimmed,
      )
    },
    [conversationId, run],
  )

  const regenerate = useCallback(() => {
    // Hide the reply being replaced straight away.
    queryClient.setQueryData(messagesKey, (current) =>
      current && current.at(-1)?.role === 'assistant' ? current.slice(0, -1) : current,
    )
    void run(`/api/v1/conversations/${conversationId}/regenerate`, undefined, null)
  }, [conversationId, messagesKey, queryClient, run])

  return {
    messages: messages.data ?? [],
    isLoading: messages.isPending,
    loadError: messages.error,
    pending,
    isResponding: pending !== null,
    error,
    dismissError: () => setError(null),
    send,
    regenerate,
  }
}
