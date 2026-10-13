import { useQuery } from '@tanstack/react-query'
import { ListChecksIcon } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { stagesQueryOptions } from '@/features/chat/api'
import { StageChecklist } from '@/features/chat/components/stage-checklist'
import { useWorkspace } from '@/features/chat/workspace-context'
import type { Schemas } from '@/lib/api/client'

/**
 * A stage's checklist inside a message. It shows the live state rather than a
 * snapshot from when the message was written, so ticking here, in the stage
 * sheet, or by the mentor all stay in step.
 */
export function ChecklistBlock({ block }: { block: Schemas['ChecklistBlock'] }) {
  const workspace = useWorkspace()
  const stages = useQuery({
    ...stagesQueryOptions(workspace?.projectId ?? ''),
    enabled: workspace !== null,
  })
  const stage = stages.data?.find((candidate) => candidate.key === block.stage_key)

  if (!workspace) return null
  if (!stage) return <Skeleton className="h-32 rounded-2xl" />

  const done = stage.checklist.filter((item) => item.done).length
  return (
    <section
      aria-label={`${stage.title} checklist`}
      className="rounded-2xl border bg-card p-4 shadow-soft"
    >
      <h3 className="flex items-center gap-2 font-heading text-lg font-semibold">
        <ListChecksIcon aria-hidden="true" className="size-5 text-primary" />
        {stage.title}
        <span className="ml-auto font-sans text-sm font-medium text-muted-foreground">
          {done} of {stage.checklist.length}
        </span>
      </h3>
      <div className="mt-2 -mx-2">
        <StageChecklist
          projectId={workspace.projectId}
          stage={stage}
          readOnly={stage.status === 'locked'}
        />
      </div>
    </section>
  )
}
