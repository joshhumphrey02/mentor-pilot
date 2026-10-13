import { useQuery } from '@tanstack/react-query'
import { DownloadIcon } from 'lucide-react'
import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { stagesQueryOptions } from '@/features/chat/api'
import { StageChecklist } from '@/features/chat/components/stage-checklist'
import { cn } from '@/lib/utils'

import { DataTab } from './data-tab'
import { LogbookTab } from './logbook-tab'
import { SavedTab } from './saved-tab'

const TABS = [
  ['checklist', 'Checklist'],
  ['logbook', 'Logbook'],
  ['saved', 'Saved'],
  ['data', 'Data'],
] as const
type TabKey = (typeof TABS)[number][0]

function ChecklistTab({ projectId }: { projectId: string }) {
  const stages = useQuery(stagesQueryOptions(projectId))
  const stage = stages.data?.find((candidate) => candidate.status === 'active')
  if (stages.isPending) return <Skeleton className="h-40 rounded-xl" />
  if (!stage) return <p className="text-muted-foreground">Every stage is complete. Well done!</p>
  return (
    <div>
      <p className="text-sm font-medium text-primary">
        Stage {stage.position}: {stage.title}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{stage.goal}</p>
      <div className="mt-2 -mx-2">
        <StageChecklist projectId={projectId} stage={stage} />
      </div>
    </div>
  )
}

/**
 * The learner's side of the project: checklist, logbook, saved blocks and
 * data. A side panel on wide screens and a bottom sheet on phones.
 */
export function WorkspacePanel({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<TabKey>('checklist')
  const id = useId()

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div role="tablist" aria-label="Project tools" className="grid shrink-0 grid-cols-4 gap-1 rounded-xl bg-muted p-1">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`${id}-${key}-tab`}
            aria-selected={tab === key}
            aria-controls={`${id}-${key}-panel`}
            onClick={() => setTab(key)}
            className={cn(
              'min-h-10 rounded-lg px-1 text-sm font-medium transition-colors',
              tab === key ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`${id}-${tab}-panel`}
        aria-labelledby={`${id}-${tab}-tab`}
        className="min-h-0 flex-1 overflow-y-auto py-4"
      >
        {tab === 'checklist' && <ChecklistTab projectId={projectId} />}
        {tab === 'logbook' && <LogbookTab projectId={projectId} />}
        {tab === 'saved' && <SavedTab projectId={projectId} />}
        {tab === 'data' && <DataTab projectId={projectId} />}
      </div>

      <Button asChild variant="outline" size="touch" className="shrink-0">
        <a href={`/api/v1/projects/${projectId}/export.pdf`} download>
          <DownloadIcon data-icon="inline-start" />
          Download project summary (PDF)
        </a>
      </Button>
    </div>
  )
}
