import { useQuery } from '@tanstack/react-query'
import { BookmarkIcon, Trash2Icon } from 'lucide-react'

import { BlockRenderer } from '@/components/blocks/block-renderer'
import { Skeleton } from '@/components/ui/skeleton'

import { pinsQueryOptions, useUnpin } from './api'

/** Blocks the learner saved from conversations, so they are easy to find again. */
export function SavedTab({ projectId }: { projectId: string }) {
  const pins = useQuery(pinsQueryOptions(projectId))
  const unpin = useUnpin(projectId)

  if (pins.isPending) return <Skeleton className="h-32 rounded-xl" />
  if (pins.data?.length === 0) {
    return (
      <p className="rounded-xl bg-muted p-4 text-sm text-muted-foreground">
        <BookmarkIcon aria-hidden="true" className="mr-1.5 inline size-4" />
        Tap “Save” under a diagram, circuit, materials list or anything else your mentor shows
        you, and it will be kept here.
      </p>
    )
  }

  return (
    <ul className="grid gap-4">
      {pins.data?.map((pin) => (
        <li key={pin.id}>
          <div className="mb-1 flex items-center justify-between gap-2">
            <h3 className="min-w-0 truncate font-sans text-sm font-semibold tracking-normal">
              {pin.title}
            </h3>
            <button
              type="button"
              aria-label={`Remove “${pin.title}” from saved`}
              disabled={unpin.isPending}
              onClick={() => unpin.mutate(pin.id)}
              className="grid size-11 shrink-0 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-danger"
            >
              <Trash2Icon aria-hidden="true" className="size-4" />
            </button>
          </div>
          <BlockRenderer block={pin.block} />
        </li>
      ))}
    </ul>
  )
}
