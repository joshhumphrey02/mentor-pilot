import { useQuery } from '@tanstack/react-query'
import { CheckIcon, HandshakeIcon, LockIcon } from 'lucide-react'

import { ResponsiveDialog } from '@/components/responsive-dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { stagesQueryOptions } from '../api'
import { StageChecklist } from './stage-checklist'

interface StageSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
}

/** The whole pathway: where the project is, what is done, and what comes next. */
export function StageSheet({ open, onOpenChange, projectId }: StageSheetProps) {
  const stages = useQuery({ ...stagesQueryOptions(projectId), enabled: open })

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Your project pathway"
      description="Nine stages from a first idea to the expo floor."
    >
      <ol className="-mx-1 grid max-h-[65dvh] gap-1 overflow-y-auto px-1 pb-1">
        {stages.isPending &&
          [0, 1, 2, 3].map((row) => <Skeleton key={row} className="h-12 rounded-xl" />)}

        {stages.data?.map((stage) => {
          const active = stage.status === 'active'
          const done = stage.checklist.filter((item) => item.done).length
          return (
            <li
              key={stage.key}
              aria-current={active ? 'step' : undefined}
              className={cn('rounded-2xl', active && 'border bg-card p-3 shadow-soft')}
            >
              <div className={cn('flex items-center gap-3', !active && 'px-3 py-2')}>
                <span
                  className={cn(
                    'grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold',
                    stage.status === 'completed' && 'bg-success text-background',
                    active && 'bg-primary text-primary-foreground',
                    stage.status === 'locked' && 'bg-muted text-muted-foreground',
                  )}
                >
                  {stage.status === 'completed' ? (
                    <CheckIcon aria-hidden="true" className="size-4" />
                  ) : stage.status === 'locked' ? (
                    <LockIcon aria-hidden="true" className="size-3.5" />
                  ) : (
                    stage.position
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      'font-medium',
                      stage.status === 'locked' && 'text-muted-foreground',
                    )}
                  >
                    <span className="sr-only">
                      Stage {stage.position}, {stage.status}:{' '}
                    </span>
                    {stage.title}
                  </p>
                  {stage.handoff && (
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <HandshakeIcon aria-hidden="true" className="size-3.5" />
                      A human mentor can join here
                    </p>
                  )}
                </div>
                {stage.status !== 'locked' && (
                  <span className="shrink-0 text-sm text-muted-foreground tabular-nums">
                    {done}/{stage.checklist.length}
                  </span>
                )}
              </div>

              {active && (
                <>
                  <p className="mt-2 text-sm text-muted-foreground">{stage.goal}</p>
                  <div className="mt-1 -mx-2">
                    <StageChecklist projectId={projectId} stage={stage} />
                  </div>
                </>
              )}
            </li>
          )
        })}
      </ol>
    </ResponsiveDialog>
  )
}
