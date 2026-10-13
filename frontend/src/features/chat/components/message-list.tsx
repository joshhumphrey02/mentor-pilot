import { ArrowDownIcon } from 'lucide-react'
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { BlockRenderer, BlockSkeleton } from '@/components/blocks/block-renderer'
import { MarkdownBlock } from '@/components/blocks/markdown-block'
import { LogoMark } from '@/components/brand/logo'

import type { Message } from '../api'
import type { PendingTurn } from '../use-chat'
import { MessageActions } from './message-actions'

// How close to the bottom still counts as "following the conversation".
const STICK_THRESHOLD_PX = 96

interface MessageListProps {
  messages: Message[]
  pending: PendingTurn | null
  empty: ReactNode
  onRegenerate: () => void
  onQuickReply: (text: string) => void
}

function UserBubble({ text, sending }: { text: string; sending?: boolean }) {
  return (
    <div className="flex justify-end">
      <p
        className={`max-w-[85%] rounded-3xl rounded-br-lg bg-primary px-4 py-2.5 whitespace-pre-wrap text-primary-foreground [overflow-wrap:anywhere] ${sending ? 'opacity-70' : ''}`}
      >
        {text}
      </p>
    </div>
  )
}

function MentorRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-3">
      <LogoMark className="mt-0.5 size-7 shrink-0" />
      <div className="grid min-w-0 flex-1 gap-3">{children}</div>
    </div>
  )
}

function Thinking({ label }: { label: string | null }) {
  return (
    <p role="status" className="flex h-7 items-center gap-2 text-sm text-muted-foreground">
      <span aria-hidden="true" className="flex gap-1">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      {label ?? <span className="sr-only">Your mentor is thinking</span>}
    </p>
  )
}

export function MessageList({
  messages,
  pending,
  empty,
  onRegenerate,
  onQuickReply,
}: MessageListProps) {
  const scroller = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const following = useRef(true)
  const [showJump, setShowJump] = useState(false)

  const toBottom = (behavior: ScrollBehavior = 'auto') => {
    const element = scroller.current
    if (element) element.scrollTo({ top: element.scrollHeight, behavior })
  }

  // Start at the latest message, before the first paint.
  useLayoutEffect(() => toBottom(), [])

  // Follow the reply as it grows, but only while the learner is at the
  // bottom. If they have scrolled up to re-read something, leave them there.
  useEffect(() => {
    const target = content.current
    if (!target) return
    const observer = new ResizeObserver(() => {
      if (following.current) toBottom()
    })
    observer.observe(target)
    return () => observer.disconnect()
  }, [])

  // Sending a message always brings you back to the bottom.
  const sending = pending?.userText
  useEffect(() => {
    if (sending) {
      following.current = true
      toBottom('smooth')
    }
  }, [sending])

  const onScroll = () => {
    const element = scroller.current
    if (!element) return
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight
    following.current = distance < STICK_THRESHOLD_PX
    setShowJump(!following.current)
  }

  const lastId = messages.at(-1)?.id
  const isEmpty = messages.length === 0 && !pending

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={scroller}
        onScroll={onScroll}
        className="h-full overflow-y-auto overscroll-contain"
        // Announces new replies to screen readers without stealing focus.
        role="log"
        aria-live="polite"
        aria-relevant="additions"
      >
        <div ref={content} className="mx-auto grid w-full max-w-3xl gap-6 px-safe py-6">
          {isEmpty && empty}

          {messages.map((message) =>
            message.role === 'user' ? (
              <UserBubble
                key={message.id}
                text={message.blocks[0]?.type === 'markdown' ? message.blocks[0].text : ''}
              />
            ) : (
              <MentorRow key={message.id}>
                {message.blocks.map((block, index) => (
                  // Blocks never reorder within a saved message.
                  // oxlint-disable-next-line react/no-array-index-key
                  <BlockRenderer key={index} block={block} onRetry={onRegenerate} />
                ))}
                {message.status === 'complete' && !pending && (
                  <MessageActions
                    message={message}
                    isLatest={message.id === lastId}
                    onRegenerate={onRegenerate}
                    onQuickReply={onQuickReply}
                  />
                )}
              </MentorRow>
            ),
          )}

          {pending?.userText && <UserBubble text={pending.userText} sending />}

          {pending && (
            <MentorRow>
              {pending.blocks.map((draft, index) => {
                if (!draft) return null
                // oxlint-disable-next-line react/no-array-index-key
                if (draft.state === 'done') return <BlockRenderer key={index} block={draft.block} />
                if (draft.state === 'writing') {
                  // oxlint-disable-next-line react/no-array-index-key
                  return <MarkdownBlock key={index} text={draft.text} streaming />
                }
                // oxlint-disable-next-line react/no-array-index-key
                return <BlockSkeleton key={index} kind={draft.kind} />
              })}
              {(pending.blocks.length === 0 || pending.toolStatus) && (
                <Thinking label={pending.toolStatus} />
              )}
            </MentorRow>
          )}
        </div>
      </div>

      {showJump && (
        <button
          type="button"
          onClick={() => {
            following.current = true
            toBottom('smooth')
          }}
          aria-label="Jump to the latest message"
          className="absolute bottom-3 left-1/2 grid size-11 -translate-x-1/2 place-items-center rounded-full border bg-card shadow-soft"
        >
          <ArrowDownIcon aria-hidden="true" className="size-5" />
        </button>
      )}
    </div>
  )
}
