import { CircuitBoardIcon } from 'lucide-react'
import { lazy, Suspense } from 'react'

import { Skeleton } from '@/components/ui/skeleton'
import type { Schemas } from '@/lib/api/client'

// The breadboard renderer is its own chunk: only conversations about
// circuits should download it.
const CircuitView = lazy(() => import('@/features/circuit/circuit-view'))

interface CircuitBlockProps {
  block: Schemas['CircuitBlock']
  photos?: boolean
}

export function CircuitBlock({ block, photos }: CircuitBlockProps) {
  return (
    <section aria-label={block.title} className="rounded-2xl border bg-card p-4 shadow-soft">
      <h3 className="mb-3 flex items-center gap-2 font-heading text-lg leading-snug font-semibold">
        <CircuitBoardIcon aria-hidden="true" className="size-5 shrink-0 text-primary" />
        {block.title}
      </h3>
      <Suspense fallback={<Skeleton className="h-72 w-full rounded-2xl" />}>
        <CircuitView block={block} photos={photos} />
      </Suspense>
    </section>
  )
}
