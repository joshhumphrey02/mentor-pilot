import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { UsersRoundIcon } from 'lucide-react'

import { EmptyState } from '@/components/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { useUser } from '@/features/auth/api'
import {
  mentorProfileQueryOptions,
  myRequestsQueryOptions,
  openRequestsQueryOptions,
} from '@/features/mentoring/api'
import { MentorProfileForm } from '@/features/mentoring/mentor-profile-form'
import { RequestCard } from '@/features/mentoring/request-card'

export const Route = createFileRoute('/app/mentor')({ component: MentorPage })

function MentorPage() {
  const user = useUser()
  return user.role === 'mentor' ? <MentorDashboard /> : <LearnerRequests />
}

function LearnerRequests() {
  const requests = useQuery(myRequestsQueryOptions)
  return (
    <>
      <h1 className="text-3xl font-semibold">Human mentors</h1>
      <p className="mt-1 text-muted-foreground">
        Real people who can help you build, find materials or get into a lab.
      </p>
      <div className="mt-8 grid gap-4">
        {requests.isPending && <Skeleton className="h-40 rounded-2xl" />}
        {requests.data?.length === 0 && (
          <EmptyState icon={UsersRoundIcon} title="No mentor requests yet">
            When your project is ready to build, your AI mentor will offer to connect you with a
            human mentor. Your requests and messages will show up here.
          </EmptyState>
        )}
        {requests.data?.map((request) => (
          <RequestCard key={request.id} request={request} viewer="learner" />
        ))}
      </div>
    </>
  )
}

function MentorDashboard() {
  const profile = useQuery(mentorProfileQueryOptions)
  const approved = profile.data?.is_approved === true
  const open = useQuery({ ...openRequestsQueryOptions, enabled: approved })
  const mine = useQuery(myRequestsQueryOptions)

  return (
    <div className="grid gap-10">
      <header>
        <h1 className="text-3xl font-semibold">Mentor dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Learners near you who need hands-on help with their expo projects.
        </p>
      </header>

      {approved && (
        <section aria-labelledby="open-heading" className="grid gap-4">
          <h2 id="open-heading" className="text-xl font-semibold">
            Open requests for you
          </h2>
          {open.isPending && <Skeleton className="h-32 rounded-2xl" />}
          {open.data?.length === 0 && (
            <p className="rounded-2xl bg-muted p-4 text-muted-foreground">
              Nothing matching your regions and expertise right now. New requests appear here.
            </p>
          )}
          {open.data?.map((request) => (
            <RequestCard key={request.id} request={request} viewer="mentor" browsing />
          ))}
        </section>
      )}

      {mine.data && mine.data.length > 0 && (
        <section aria-labelledby="mine-heading" className="grid gap-4">
          <h2 id="mine-heading" className="text-xl font-semibold">
            Learners you are mentoring
          </h2>
          {mine.data.map((request) => (
            <RequestCard key={request.id} request={request} viewer="mentor" />
          ))}
        </section>
      )}

      <section aria-labelledby="profile-heading" className="grid gap-4">
        <h2 id="profile-heading" className="text-xl font-semibold">
          Your mentor profile
        </h2>
        <MentorProfileForm />
      </section>
    </div>
  )
}
