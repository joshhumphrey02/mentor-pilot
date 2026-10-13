import { ArrowUpIcon } from 'lucide-react'
import { type FormEvent, type KeyboardEvent, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

const MAX_LENGTH = 4000

interface ComposerProps {
  onSend: (text: string) => void
  /** True while the mentor is replying: typing is allowed, sending is not. */
  busy: boolean
  suggestions: string[]
}

export function Composer({ onSend, busy, suggestions }: ComposerProps) {
  const [text, setText] = useState('')
  const input = useRef<HTMLTextAreaElement>(null)
  const canSend = text.trim().length > 0 && !busy

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (!canSend) return
    onSend(text)
    setText('')
    // Keep the keyboard open on phones: sending should not dismiss it.
    input.current?.focus()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends with a physical keyboard. On touch screens Enter makes a
    // new line, because there is a send button under the thumb and no Shift.
    const touch = window.matchMedia('(pointer: coarse)').matches
    if (event.key === 'Enter' && !event.shiftKey && !touch && !event.nativeEvent.isComposing) {
      submit()
      event.preventDefault()
    }
  }

  return (
    <div className="border-t bg-background/95 backdrop-blur">
      <div className="mx-auto w-full max-w-3xl px-safe pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        {suggestions.length > 0 && !busy && (
          <ul
            aria-label="Suggested replies"
            className="-mx-4 mb-2 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0"
          >
            {suggestions.map((suggestion) => (
              <li key={suggestion} className="shrink-0">
                <button
                  type="button"
                  onClick={() => onSend(suggestion)}
                  className="min-h-11 rounded-full border bg-card px-4 text-sm font-medium text-secondary-foreground hover:border-primary hover:bg-secondary"
                >
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
        )}

        <form
          onSubmit={submit}
          className="flex items-end gap-2 rounded-3xl border bg-card p-1.5 shadow-soft focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30"
        >
          <label htmlFor="chat-input" className="sr-only">
            Message your mentor
          </label>
          <textarea
            id="chat-input"
            ref={input}
            value={text}
            rows={1}
            maxLength={MAX_LENGTH}
            placeholder="Message your mentor"
            enterKeyHint="send"
            onChange={(event) => setText(event.target.value)}
            onKeyDown={onKeyDown}
            // 16px text stops iOS zooming in on focus. The field grows with
            // its content up to about six lines, then scrolls.
            className="field-sizing-content max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-base outline-none placeholder:text-muted-foreground"
          />
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send message"
            className={cn(
              'grid size-11 shrink-0 place-items-center rounded-full transition-colors',
              canSend
                ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                : 'bg-muted text-muted-foreground',
            )}
          >
            <ArrowUpIcon aria-hidden="true" className="size-5" />
          </button>
        </form>
      </div>
    </div>
  )
}
