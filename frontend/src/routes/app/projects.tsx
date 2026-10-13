import { createFileRoute } from '@tanstack/react-router'
import { FolderKanbanIcon } from 'lucide-react'

import { EmptyState } from '@/components/empty-state'

export const Route = createFileRoute('/app/projects')({ component: ProjectsPage })

function ProjectsPage() {
  return (
    <>
      <h1 className="text-3xl font-semibold">Projects</h1>
      <div className="mt-8">
        <EmptyState icon={FolderKanbanIcon} title="No projects yet">
          When you start a project it will appear here, with its stage and what to do next.
        </EmptyState>
      </div>
    </>
  )
}
