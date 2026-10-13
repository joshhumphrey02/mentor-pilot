import { ArrowRightIcon, PartyPopperIcon } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useAdvanceStage } from '@/features/chat/api'
import { useWorkspace } from '@/features/chat/workspace-context'
import { stagePosition } from '@/features/pathway/stages'
import type { Schemas } from '@/lib/api/client'
import { errorMessage } from '@/lib/api/errors'

const CONFETTI = [
  ['8%', 'var(--spark)', '0ms'],
  ['22%', 'var(--chart-2)', '120ms'],
  ['37%', 'var(--primary-foreground)', '60ms'],
  ['52%', 'var(--spark)', '200ms'],
  ['66%', 'var(--chart-4)', '30ms'],
  ['80%', 'var(--primary-foreground)', '160ms'],
  ['92%', 'var(--chart-2)', '90ms'],
] as const

/**
 * The mentor's proposal to move on. Until the learner confirms, nothing has
 * changed. Once the project is past this stage the card becomes a celebration.
 */
export function StageTransitionBlock({ block }: { block: Schemas['StageTransitionBlock'] }) {
  const workspace = useWorkspace()
  const advance = useAdvanceStage(workspace?.projectId ?? '')
  if (!workspace) return null

  const here = stagePosition(workspace.currentStage).number
  const completed = here > stagePosition(block.from_stage).number

  if (completed) {
    return (
      <section
        aria-label="Stage complete"
        className="relative overflow-hidden rounded-2xl bg-primary p-5 text-primary-foreground"
      >
        {/* Decorative, and still for anyone who prefers reduced motion. */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          {CONFETTI.map(([left, background, delay]) => (
            <span
              key={left}
              className="confetti-piece absolute top-0 h-3 w-1.5 rounded-sm"
              style={{ left, background, animationDelay: delay }}
            />
          ))}
        </div>
        <PartyPopperIcon aria-hidden="true" className="size-7 text-spark" />
        <h3 className="mt-2 font-heading text-xl font-semibold">{block.from_title} complete</h3>
        <p className="mt-1 opacity-90">{block.summary}</p>
        <p className="mt-3 inline-flex items-center gap-2 text-sm font-medium">
          Next up: {block.to_title}
          <ArrowRightIcon aria-hidden="true" className="size-4" />
        </p>
      </section>
    )
  }

  return (
    <section
      aria-label="Ready for the next stage?"
      className="rounded-2xl border-2 border-primary/30 bg-secondary p-5"
    >
      <h3 className="font-heading text-lg font-semibold">Ready for {block.to_title}?</h3>
      <p className="mt-1">{block.summary}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          size="touch"
          disabled={advance.isPending || workspace.busy}
          onClick={async () => {
            try {
              await advance.mutateAsync(block.from_stage)
              workspace.send(`I'm ready for ${block.to_title}.`)
            } catch (error) {
              toast.error(errorMessage(error))
            }
          }}
        >
          {advance.isPending ? 'Moving on…' : 'Yes, move on'}
          <ArrowRightIcon data-icon="inline-end" />
        </Button>
        <Button
          variant="outline"
          size="touch"
          className="bg-background"
          disabled={workspace.busy}
          onClick={() => workspace.send(`Not yet. I want to keep working on ${block.from_title}.`)}
        >
          Not yet
        </Button>
      </div>
    </section>
  )
}
