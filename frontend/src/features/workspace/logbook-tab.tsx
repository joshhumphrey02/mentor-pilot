import { useQuery } from '@tanstack/react-query'
import { Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/api/errors'

import { logbookQueryOptions, useAddLogbookEntry, useDeleteLogbookEntry } from './api'

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

/** The learner's own dated notes: what they did, saw and decided. */
export function LogbookTab({ projectId }: { projectId: string }) {
  const entries = useQuery(logbookQueryOptions(projectId))
  const add = useAddLogbookEntry(projectId)
  const remove = useDeleteLogbookEntry(projectId)
  const [text, setText] = useState('')

  return (
    <div className="grid gap-4">
      <form
        className="grid gap-2"
        onSubmit={async (event) => {
          event.preventDefault()
          if (!text.trim()) return
          try {
            await add.mutateAsync(text)
            setText('')
          } catch (error) {
            toast.error(errorMessage(error))
          }
        }}
      >
        <label htmlFor="logbook-entry" className="text-sm font-medium">
          What did you do today?
        </label>
        <textarea
          id="logbook-entry"
          value={text}
          rows={3}
          maxLength={5000}
          onChange={(event) => setText(event.target.value)}
          placeholder="What you tried, what happened, what you'll do next…"
          className="field-sizing-content max-h-48 min-h-20 rounded-xl border border-input bg-transparent px-3.5 py-2.5 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
        <Button type="submit" size="touch" disabled={!text.trim() || add.isPending} className="justify-self-start">
          {add.isPending ? 'Saving…' : 'Add to logbook'}
        </Button>
      </form>

      {entries.isPending && <Skeleton className="h-20 rounded-xl" />}
      {entries.data?.length === 0 && (
        <p className="rounded-xl bg-muted p-4 text-sm text-muted-foreground">
          Judges read logbooks. Short, dated notes written as you go are worth more than a neat
          summary written at the end, mistakes included.
        </p>
      )}
      <ol className="grid gap-3">
        {entries.data?.map((entry) => (
          <li key={entry.id} className="rounded-xl border bg-card p-3">
            <div className="flex items-start justify-between gap-2">
              <time dateTime={entry.created_at} className="text-xs font-medium text-muted-foreground">
                {dateFormat.format(new Date(entry.created_at))}
              </time>
              <button
                type="button"
                aria-label="Delete this entry"
                disabled={remove.isPending}
                onClick={() => remove.mutate(entry.id)}
                className="-mt-2 -mr-2 grid size-11 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-danger"
              >
                <Trash2Icon aria-hidden="true" className="size-4" />
              </button>
            </div>
            <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{entry.text}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}
