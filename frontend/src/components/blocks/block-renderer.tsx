import { Skeleton } from '@/components/ui/skeleton'
import type { Block } from '@/features/chat/api'

import { BomTableBlock } from './bom-table-block'
import { CalloutBlock } from './callout-block'
import { ChartBlock } from './chart-block'
import { ChecklistBlock } from './checklist-block'
import { CircuitBlock } from './circuit-block'
import { ComparisonTableBlock } from './comparison-table-block'
import { DiagramBlock } from './diagram-block'
import { ErrorBlock } from './error-block'
import { ExperimentPlanBlock } from './experiment-plan-block'
import { IdeaCardsBlock } from './idea-cards-block'
import { ImageGalleryBlock } from './image-gallery-block'
import { MarkdownBlock } from './markdown-block'
import { QuizBlock } from './quiz-block'
import { StageTransitionBlock } from './stage-transition-block'
import { VideoCardsBlock } from './video-cards-block'

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
    case 'idea_cards':
      return <IdeaCardsBlock block={block} />
    case 'comparison_table':
      return <ComparisonTableBlock block={block} />
    case 'diagram':
      return <DiagramBlock block={block} />
    case 'image_gallery':
      return <ImageGalleryBlock block={block} />
    case 'video_cards':
      return <VideoCardsBlock block={block} />
    case 'chart':
      return <ChartBlock block={block} />
    case 'checklist':
      return <ChecklistBlock block={block} />
    case 'experiment_plan':
      return <ExperimentPlanBlock block={block} />
    case 'bom_table':
      return <BomTableBlock block={block} />
    case 'quiz':
      return <QuizBlock block={block} />
    case 'circuit':
      return <CircuitBlock block={block} />
    case 'stage_transition':
      return <StageTransitionBlock block={block} />
    case 'suggested_replies':
      // Rendered as chips above the input, not inside the message.
      return null
    default:
      // A block type newer than this build of the app (an old cached page
      // against a newer server): skip it rather than crash.
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
