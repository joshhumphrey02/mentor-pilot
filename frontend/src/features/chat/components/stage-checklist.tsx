import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'

import { type Stage, useSetChecklistItem } from '../api'

interface StageChecklistProps {
  projectId: string
  stage: Stage
  /** Locked stages show what is coming but cannot be ticked yet. */
  readOnly?: boolean
}

/** A stage's deliverables. The learner and the mentor can both tick them. */
export function StageChecklist({ projectId, stage, readOnly }: StageChecklistProps) {
  const setItem = useSetChecklistItem(projectId)

  return (
    <ul className="grid gap-1">
      {stage.checklist.map((item) => (
        <li key={item.key}>
          <label
            className={cn(
              'flex min-h-11 items-start gap-3 rounded-xl px-2 py-2.5',
              !readOnly && 'cursor-pointer hover:bg-muted',
            )}
          >
            <Checkbox
              checked={item.done}
              disabled={readOnly}
              onCheckedChange={(checked) =>
                setItem.mutate({ stageKey: stage.key, itemKey: item.key, done: checked === true })
              }
              className="mt-0.5 size-5"
            />
            <span className="min-w-0">
              <span className={cn(item.done && 'text-muted-foreground line-through')}>
                {item.label}
              </span>
              {item.note && (
                <span className="mt-0.5 block text-sm text-muted-foreground">{item.note}</span>
              )}
            </span>
          </label>
        </li>
      ))}
    </ul>
  )
}
