import { useQuery } from '@tanstack/react-query'
import { SendIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api/errors'
import { cn } from '@/lib/utils'

import {
  HELP_TYPES,
  type HelpType,
  type MentorRequest,
  STATUS_LABELS,
  threadQueryOptions,
  useRequestAction,
  useSendThreadMessage,
} from './api'

const STATUS_TONE: Record<MentorRequest['status'], string> = {
  pending: 'bg-warning-soft text-warning',
  matched: 'bg-info-soft text-info',
  in_progress: 'bg-info-soft text-info',
  completed: 'bg-success-soft text-success',
  cancelled: 'bg-muted text-muted-foreground',
}
const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

function Thread({ request }: { request: MentorRequest }) {
  const thread = useQuery(threadQueryOptions(request.id))
  const send = useSendThreadMessage(request.id)
  const [text, setText] = useState('')
  const open = request.status === 'matched' || request.status === 'in_progress'

  return (
    <div className="mt-4 border-t pt-4">
      <ol aria-label="Messages" className="grid gap-2">
        {thread.data?.length === 0 && (
          <li className="text-sm text-muted-foreground">No messages yet. Say hello.</li>
        )}
        {thread.data?.map((message) => (
          <li key={message.id} className={cn('flex', message.mine && 'justify-end')}>
            <div
              className={cn(
                'max-w-[85%] rounded-2xl px-3.5 py-2',
                message.mine ? 'rounded-br-md bg-primary text-primary-foreground' : 'rounded-bl-md bg-muted',
              )}
            >
              <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{message.text}</p>
              <p className="mt-0.5 text-xs opacity-70">
                {message.mine ? 'You' : (message.sender?.first_name ?? 'Someone')} ·{' '}
                {timeFormat.format(new Date(message.created_at))}
              </p>
            </div>
          </li>
        ))}
      </ol>

      {open ? (
        <form
          className="mt-3 flex items-end gap-2"
          onSubmit={async (event) => {
            event.preventDefault()
            if (!text.trim()) return
            try {
              await send.mutateAsync(text.trim())
              setText('')
            } catch (error) {
              toast.error(errorMessage(error))
            }
          }}
        >
          <label htmlFor={`thread-${request.id}`} className="sr-only">
            Message
          </label>
          <textarea
            id={`thread-${request.id}`}
            value={text}
            rows={1}
            maxLength={2000}
            placeholder="Write a message"
            onChange={(event) => setText(event.target.value)}
            className="field-sizing-content max-h-32 min-h-11 flex-1 resize-none rounded-2xl border border-input bg-transparent px-3.5 py-2.5 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
          <Button type="submit" size="icon-touch" disabled={!text.trim() || send.isPending} aria-label="Send">
            <SendIcon />
          </Button>
        </form>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          {request.status === 'pending'
            ? 'You can message each other once a mentor accepts.'
            : 'This conversation is closed.'}
        </p>
      )}
      <p className="mt-2 text-xs text-muted-foreground">
        Keep it on Mentor Pilot: phone numbers, emails and social media can't be shared here.
      </p>
    </div>
  )
}

interface RequestCardProps {
  request: MentorRequest
  /** Whose view this is: decides which actions are offered. */
  viewer: 'learner' | 'mentor'
  /** An unmatched request a mentor is browsing: show Accept, hide the thread. */
  browsing?: boolean
}

export function RequestCard({ request, viewer, browsing }: RequestCardProps) {
  const act = useRequestAction()
  const run = (action: Parameters<typeof act.mutate>[0]['action']) =>
    act.mutate({ requestId: request.id, action }, { onError: (error) => toast.error(errorMessage(error)) })
  const idea = request.snapshot.idea as { problem?: string } | undefined
  const closed = request.status === 'completed' || request.status === 'cancelled'

  return (
    <article className="rounded-2xl border bg-card p-4 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-heading text-lg leading-snug font-semibold">{request.project_title}</h3>
          <p className="text-sm text-muted-foreground">
            {viewer === 'mentor'
              ? [request.learner.first_name, request.school_name, request.province].filter(Boolean).join(' · ')
              : request.mentor
                ? `Your mentor: ${request.mentor.first_name}`
                : 'No mentor yet'}
          </p>
        </div>
        <span className={cn('rounded-full px-2.5 py-1 text-xs font-semibold', STATUS_TONE[request.status])}>
          {STATUS_LABELS[request.status]}
        </span>
      </div>

      <ul aria-label="Help needed" className="mt-3 flex flex-wrap gap-1.5">
        {request.help_types.map((type) => (
          <li key={type} className="rounded-full bg-muted px-2.5 py-0.5 text-sm">
            {HELP_TYPES[type as HelpType] ?? type}
          </li>
        ))}
      </ul>
      <p className="mt-3 whitespace-pre-wrap">{request.description}</p>
      {viewer === 'mentor' && (
        <p className="mt-2 text-sm text-muted-foreground">
          Stage: {String(request.snapshot.stage ?? '')}
          {idea?.problem ? ` · Problem: ${idea.problem}` : ''}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {browsing && (
          <Button size="touch" disabled={act.isPending} onClick={() => run('accept')}>
            Accept this request
          </Button>
        )}
        {viewer === 'mentor' && request.status === 'matched' && (
          <Button variant="outline" size="touch" disabled={act.isPending} onClick={() => run('in_progress')}>
            Mark as in progress
          </Button>
        )}
        {viewer === 'mentor' && (request.status === 'matched' || request.status === 'in_progress') && (
          <Button variant="outline" size="touch" disabled={act.isPending} onClick={() => run('completed')}>
            Mark as completed
          </Button>
        )}
        {viewer === 'learner' && !closed && (
          <Button variant="outline" size="touch" disabled={act.isPending} onClick={() => run('cancel')}>
            Cancel request
          </Button>
        )}
      </div>

      {!browsing && <Thread request={request} />}
    </article>
  )
}
