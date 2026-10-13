import { CheckIcon, CopyIcon, RotateCwIcon, ThumbsDownIcon, ThumbsUpIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { cn } from '@/lib/utils'

import { type Message, messageText, useFeedback } from '../api'

interface MessageActionsProps {
  message: Message
  /** Only the latest reply can be regenerated or followed up on. */
  isLatest: boolean
  onRegenerate: () => void
  onQuickReply: (text: string) => void
}

const action =
  'grid size-11 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground sm:size-9'

export function MessageActions({
  message,
  isLatest,
  onRegenerate,
  onQuickReply,
}: MessageActionsProps) {
  const feedback = useFeedback(message.conversation_id)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(messageText(message))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error("Couldn't copy that. Try selecting the text instead.")
    }
  }

  const rate = (value: 1 | -1) =>
    feedback.mutate({ messageId: message.id, value: message.feedback === value ? 0 : value })

  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-1 gap-y-2">
      <button type="button" className={action} onClick={copy} aria-label="Copy reply">
        {copied ? (
          <CheckIcon aria-hidden="true" className="size-4.5 text-success" />
        ) : (
          <CopyIcon aria-hidden="true" className="size-4.5" />
        )}
      </button>
      <button
        type="button"
        className={cn(action, message.feedback === 1 && 'bg-secondary text-primary')}
        onClick={() => rate(1)}
        aria-label="This was helpful"
        aria-pressed={message.feedback === 1}
      >
        <ThumbsUpIcon aria-hidden="true" className="size-4.5" />
      </button>
      <button
        type="button"
        className={cn(action, message.feedback === -1 && 'bg-secondary text-primary')}
        onClick={() => rate(-1)}
        aria-label="This was not helpful"
        aria-pressed={message.feedback === -1}
      >
        <ThumbsDownIcon aria-hidden="true" className="size-4.5" />
      </button>
      {isLatest && (
        <>
          <button type="button" className={action} onClick={onRegenerate} aria-label="Try again">
            <RotateCwIcon aria-hidden="true" className="size-4.5" />
          </button>
          <span className="ml-auto flex gap-2">
            {(
              [
                ['Explain simpler', 'Can you explain that more simply?'],
                ['Go deeper', 'Can you go deeper on that?'],
              ] as const
            ).map(([label, text]) => (
              <button
                key={label}
                type="button"
                onClick={() => onQuickReply(text)}
                className="min-h-11 rounded-full px-3 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground sm:min-h-9"
              >
                {label}
              </button>
            ))}
          </span>
        </>
      )}
    </div>
  )
}
