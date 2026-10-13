import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link, redirect } from '@tanstack/react-router'
import { ArrowRightIcon, CalendarDaysIcon, LightbulbIcon } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/empty-state'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { meQueryOptions, useUser } from '@/features/auth/api'
import { projectsQueryOptions } from '@/features/chat/api'
import { NewProjectButton } from '@/features/chat/components/new-project-button'
import { ProjectCard } from '@/features/chat/components/project-card'
import { expoEventsQueryOptions } from '@/features/mentoring/api'
import { stagePosition } from '@/features/pathway/stages'

export const Route = createFileRoute('/app/')({
  beforeLoad: async ({ context }) => {
    const user = await context.queryClient.ensureQueryData(meQueryOptions)
    // A mentor's home is their requests; projects are a learner's thing.
    if (user?.role === 'mentor') throw redirect({ to: '/app/mentor' })
  },
  component: DashboardPage,
})

const EXPO_DATE = new Intl.DateTimeFormat(undefined, { dateStyle: 'long' })

function greeting(hour: number) {
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function DashboardPage() {
  const user = useUser()
  const firstName = user.full_name.split(' ')[0] || 'there'
  // Read the clock once: render must stay pure.
  const [hour] = useState(() => new Date().getHours())
  const projects = useQuery(projectsQueryOptions)
  const active = projects.data?.filter((project) => project.status === 'active') ?? []
  const [latest, ...others] = active
  const expos = useQuery(expoEventsQueryOptions)

  return (
    <>
      <h1 className="text-3xl font-semibold">
        {greeting(hour)}, {firstName}
      </h1>
      <p className="mt-1 text-muted-foreground">Ready to build something for the expo?</p>

      <div className="mt-8 grid gap-8">
        {projects.isPending && <Skeleton className="h-40 rounded-3xl" />}

        {projects.data && !latest && (
          <EmptyState
            icon={LightbulbIcon}
            title="Every project starts with a problem"
            action={<NewProjectButton />}
          >
            Your mentor will help you spot one worth solving in your community, school or home.
          </EmptyState>
        )}

        {latest && (
          <section
            aria-labelledby="continue-heading"
            className="relative overflow-hidden rounded-3xl bg-primary p-6 text-primary-foreground"
          >
            <div
              aria-hidden="true"
              className="bg-grid absolute inset-0 opacity-50 invert dark:invert-0"
            />
            <div className="relative">
              <p id="continue-heading" className="text-sm font-medium opacity-80">
                Continue where you left off
              </p>
              <h2 className="mt-1 text-2xl font-semibold">{latest.title}</h2>
              <p className="mt-1 opacity-80">
                Stage {stagePosition(latest.current_stage).number}:{' '}
                {stagePosition(latest.current_stage).title}
              </p>
              <Button
                asChild
                size="touch"
                className="mt-5 bg-primary-foreground text-primary hover:bg-primary-foreground/90"
              >
                <Link to="/project/$projectId" params={{ projectId: latest.id }}>
                  Open project
                  <ArrowRightIcon data-icon="inline-end" />
                </Link>
              </Button>
            </div>
          </section>
        )}

        {latest && (
          <section aria-labelledby="projects-heading" className="grid gap-3">
            {/* Wraps on narrow phones: the button is wider than the space beside the heading. */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="projects-heading" className="text-xl font-semibold">
                Your projects
              </h2>
              <NewProjectButton variant="outline" />
            </div>
            {others.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Just the one for now. You can run several projects side by side.
              </p>
            ) : (
              others.map((project) => <ProjectCard key={project.id} project={project} />)
            )}
          </section>
        )}
        {expos.data && expos.data.length > 0 && (
          <section aria-labelledby="expos-heading" className="grid gap-3">
            <h2 id="expos-heading" className="text-xl font-semibold">
              Upcoming expos
            </h2>
            <ul className="grid gap-2">
              {expos.data.map((expo) => (
                <li key={expo.id} className="flex items-center gap-3 rounded-2xl border bg-card p-3">
                  <CalendarDaysIcon aria-hidden="true" className="size-5 shrink-0 text-primary" />
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{expo.name}</span>
                    <span className="block truncate text-sm text-muted-foreground">
                      {EXPO_DATE.format(new Date(`${expo.starts_on}T00:00:00`))}
                      {expo.location ? ` · ${expo.location}` : ''}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </>
  )
}
