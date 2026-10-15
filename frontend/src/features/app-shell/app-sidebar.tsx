import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { MoreHorizontalIcon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Logo } from '@/components/brand/logo'
import { FormAlert } from '@/components/form/fields'
import { ResponsiveDialog } from '@/components/responsive-dialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { navFor } from '@/features/app-shell/nav'
import { useUser } from '@/features/auth/api'
import { type Project, projectsQueryOptions, useDeleteProject } from '@/features/chat/api'
import { errorMessage } from '@/lib/api/errors'

const ITEM_CLASS =
  'flex items-center rounded-xl text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[status=active]:bg-sidebar-accent data-[status=active]:text-sidebar-accent-foreground'

/**
 * The sidebar of every signed-in page from `md` up, the project workspace
 * included: the main destinations, then the learner's projects.
 */
export function AppSidebar() {
  const items = navFor(useUser().role)
  const hasProjects = items.some((item) => item.to === '/app/projects')

  return (
    <aside className="sticky top-0 hidden h-dvh flex-col border-r bg-sidebar p-4 md:flex">
      <Link to="/app" className="rounded-lg px-2 py-1.5" aria-label="Mentor Pilot home">
        <Logo />
      </Link>
      <nav aria-label="Main" className="mt-8 grid gap-1">
        {items.map(({ to, label, icon: Icon, exact }) => (
          <Link
            key={to}
            to={to}
            activeOptions={{ exact }}
            className={`${ITEM_CLASS} h-11 gap-3 px-3 font-medium`}
          >
            <Icon aria-hidden="true" className="size-5" />
            {label}
          </Link>
        ))}
      </nav>
      {hasProjects && <ProjectList />}
    </aside>
  )
}

function ProjectList() {
  const projects = useQuery(projectsQueryOptions)
  const [deleting, setDeleting] = useState<Project | null>(null)

  if (projects.data?.length === 0) return null

  return (
    <nav aria-labelledby="sidebar-projects" className="mt-6 flex min-h-0 flex-1 flex-col">
      <h2
        id="sidebar-projects"
        className="px-3 pb-2 font-sans text-xs font-semibold tracking-normal text-muted-foreground uppercase"
      >
        Your projects
      </h2>
      <ul className="-mx-1 grid min-h-0 content-start gap-0.5 overflow-y-auto px-1">
        {projects.isPending &&
          [0, 1, 2].map((row) => <Skeleton key={row} className="h-10 rounded-xl" />)}
        {projects.data?.map((project) => (
          <li key={project.id} className="group relative">
            <Link
              to="/project/$projectId"
              params={{ projectId: project.id }}
              className={`${ITEM_CLASS} h-10 pr-10 pl-3 text-sm`}
            >
              <span className="truncate">{project.title}</span>
            </Link>
            <ProjectMenu project={project} onDelete={() => setDeleting(project)} />
          </li>
        ))}
      </ul>
      <DeleteProjectDialog project={deleting} onClose={() => setDeleting(null)} />
    </nav>
  )
}

function ProjectMenu({ project, onDelete }: { project: Project; onDelete: () => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`More options for ${project.title}`}
          // Revealed on hover where there is a mouse; always shown on touch.
          className="absolute top-1 right-1 text-muted-foreground pointer-fine:opacity-0 pointer-fine:group-hover:opacity-100 pointer-fine:group-focus-within:opacity-100 pointer-fine:data-[state=open]:opacity-100"
        >
          <MoreHorizontalIcon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="right">
        <DropdownMenuItem variant="destructive" onSelect={onDelete}>
          <Trash2Icon aria-hidden="true" />
          Delete project
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function DeleteProjectDialog({ project, onClose }: { project: Project | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { projectId: openProjectId } = useParams({ strict: false })
  const remove = useDeleteProject()

  const close = () => {
    onClose()
    remove.reset()
  }

  const confirm = async () => {
    if (!project) return
    const done = await remove
      .mutateAsync(project.id)
      .then(() => true)
      .catch(() => false)
    if (!done) return
    close()
    if (openProjectId === project.id) await navigate({ to: '/app/projects' })
    queryClient.removeQueries({ queryKey: ['projects', project.id] })
    toast.success(`“${project.title}” was deleted.`)
  }

  return (
    <ResponsiveDialog
      open={project !== null}
      onOpenChange={(open) => !open && close()}
      title="Delete this project?"
      description={
        project
          ? `“${project.title}” and all its chats, logbook entries and saved items will be removed.`
          : undefined
      }
    >
      <div className="grid gap-4">
        {remove.error && <FormAlert>{errorMessage(remove.error)}</FormAlert>}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" size="touch" onClick={close}>
            Keep it
          </Button>
          <Button
            type="button"
            size="touch"
            disabled={remove.isPending}
            onClick={confirm}
            className="bg-danger text-background hover:bg-danger/90"
          >
            {remove.isPending ? 'Deleting…' : 'Delete project'}
          </Button>
        </div>
      </div>
    </ResponsiveDialog>
  )
}
