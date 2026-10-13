import { Maximize2Icon, MinusIcon, PlusIcon } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import type { Schemas } from '@/lib/api/client'

const DiagramRenderer = lazy(() => import('./diagram-renderer'))

const ZOOM_STEPS = [1, 1.5, 2, 3]

export function DiagramBlock({ block }: { block: Schemas['DiagramBlock'] }) {
  const [open, setOpen] = useState(false)
  const [zoom, setZoom] = useState(0)
  const scale = ZOOM_STEPS[zoom] ?? 1
  const diagram = (
    <Suspense fallback={<Skeleton className="h-40 w-full rounded-xl" />}>
      <DiagramRenderer source={block.mermaid} label={block.title} />
    </Suspense>
  )

  return (
    <figure className="rounded-2xl border bg-card p-4 shadow-soft">
      <div className="mb-3 flex items-start justify-between gap-2">
        <figcaption className="font-heading text-lg leading-snug font-semibold">
          {block.title}
        </figcaption>
        <Button
          variant="ghost"
          size="icon-touch"
          className="-mt-2 -mr-2 shrink-0"
          aria-label={`View “${block.title}” full screen`}
          onClick={() => {
            setZoom(0)
            setOpen(true)
          }}
        >
          <Maximize2Icon />
        </Button>
      </div>
      <div className="overflow-x-auto">{diagram}</div>
      {block.caption && <p className="mt-3 text-sm text-muted-foreground">{block.caption}</p>}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="flex h-dvh max-h-dvh w-screen max-w-none flex-col gap-0 rounded-none p-0 sm:max-w-none">
          <div className="flex items-center gap-2 border-b py-2 pr-14 pl-4">
            <DialogTitle className="min-w-0 flex-1 truncate">{block.title}</DialogTitle>
            <DialogDescription className="sr-only">
              Full-screen diagram. Use the buttons to zoom, and scroll to move around.
            </DialogDescription>
            <Button
              variant="outline"
              size="icon-touch"
              aria-label="Zoom out"
              disabled={zoom === 0}
              onClick={() => setZoom((value) => Math.max(0, value - 1))}
            >
              <MinusIcon />
            </Button>
            <Button
              variant="outline"
              size="icon-touch"
              aria-label="Zoom in"
              disabled={zoom === ZOOM_STEPS.length - 1}
              onClick={() => setZoom((value) => Math.min(ZOOM_STEPS.length - 1, value + 1))}
            >
              <PlusIcon />
            </Button>
          </div>
          {/* touch-action lets two fingers pinch-zoom the diagram on phones. */}
          <div className="flex-1 touch-pinch-zoom overflow-auto p-4">
            <div style={{ width: `${scale * 100}%` }} className="mx-auto min-w-full">
              {diagram}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </figure>
  )
}
