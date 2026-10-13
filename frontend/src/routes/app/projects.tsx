import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { FolderKanbanIcon } from 'lucide-react'

import { EmptyState } from '@/components/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { projectsQueryOptions } from '@/features/chat/api'
import { NewProjectButton } from '@/features/chat/components/new-project-button'
import { ProjectCard } from '@/features/chat/components/project-card'

export const Route = createFileRoute('/app/projects')({ component: ProjectsPage })

function ProjectsPage() {
  const projects = useQuery(projectsQueryOptions)

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold">Projects</h1>
        {projects.data && projects.data.length > 0 && <NewProjectButton />}
      </div>

      <div className="mt-8 grid gap-3">
        {projects.isPending &&
          [0, 1].map((row) => <Skeleton key={row} className="h-20 rounded-2xl" />)}

        {projects.isError && (
          <p role="alert" className="rounded-2xl border border-danger/30 bg-danger-soft p-4 text-danger">
            We couldn't load your projects. Check your connection and try again.
          </p>
        )}

        {projects.data?.length === 0 && (
          <EmptyState icon={FolderKanbanIcon} title="No projects yet" action={<NewProjectButton />}>
            Start one and your mentor will help you find a real problem worth solving.
          </EmptyState>
        )}

        {projects.data?.map((project) => (
          <ProjectCard key={project.id} project={project} />
        ))}
      </div>
    </>
  )
}
