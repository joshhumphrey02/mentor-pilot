import { Skeleton } from '@/components/ui/skeleton'
import type { Block } from '@/features/chat/api'

import { CalloutBlock } from './callout-block'
import { ErrorBlock } from './error-block'
import { MarkdownBlock } from './markdown-block'

interface BlockRendererProps {
  block: Block
  onRetry?: () => void
}

/** Picks the component for a render block. One renderer per block type. */
export function BlockRenderer({ block, onRetry }: BlockRendererProps) {
  switch (block.type) {
    case 'markdown':
      return <MarkdownBlock text={block.text} />
    case 'callout':
      return <CalloutBlock block={block} />
    case 'error':
      return <ErrorBlock block={block} onRetry={onRetry} />
    case 'suggested_replies':
      // Rendered as chips above the input, not inside the message.
      return null
    default:
      // A block type newer than this build of the app: skip it rather than crash.
      return null
  }
}

/** The placeholder shown while a visual block is still being prepared. */
export function BlockSkeleton({ kind }: { kind: string }) {
  if (kind === 'suggested_replies') return null
  return (
    <div role="status" aria-label="Loading" className="rounded-2xl border p-4">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-3 h-4 w-full" />
      <Skeleton className="mt-2 h-4 w-3/4" />
    </div>
  )
}
