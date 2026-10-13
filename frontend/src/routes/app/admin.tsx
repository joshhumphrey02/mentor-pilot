import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, redirect } from '@tanstack/react-router'
import { type ReactNode, useState } from 'react'
import { toast } from 'sonner'

import { CONTROL_CLASS } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { adminActions, adminQueries, type UsageGroup, useAdminAction } from '@/features/admin/api'
import { meQueryOptions } from '@/features/auth/api'
import { HELP_TYPES, type HelpType, STATUS_LABELS } from '@/features/mentoring/api'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { api, type Schemas } from '@/lib/api/client'
import { errorMessage, unwrap } from '@/lib/api/errors'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/app/admin')({
  beforeLoad: async ({ context }) => {
    const user = await context.queryClient.ensureQueryData(meQueryOptions)
    // The API enforces this too; the redirect just avoids showing a page of errors.
    if (user?.role !== 'admin') throw redirect({ to: '/app' })
  },
  component: AdminPage,
})

const TABS = ['Usage', 'Users', 'Mentors', 'Requests', 'Schools', 'Moderation', 'AI', 'Stages'] as const
type Tab = (typeof TABS)[number]

const fail = (error: unknown) => toast.error(errorMessage(error))
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 4 })

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-2xl border">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-muted text-left">
            {head.map((cell) => (
              <th key={cell} scope="col" className="p-3 font-semibold whitespace-nowrap">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&_td]:p-3 [&_tr]:border-t">{children}</tbody>
      </table>
    </div>
  )
}

const Loading = () => <Skeleton className="h-40 rounded-2xl" />
const Empty = ({ children }: { children: ReactNode }) => (
  <p className="rounded-2xl bg-muted p-4 text-muted-foreground">{children}</p>
)

function UsageTab() {
  const [group, setGroup] = useState<UsageGroup>('day')
  const usage = useQuery(adminQueries.usage(group))
  const rows = usage.data ?? []
  const priced = rows.filter((row) => row.cost_usd !== null)
  const total = priced.reduce((sum, row) => sum + Number(row.cost_usd), 0)

  return (
    <div className="grid gap-4">
      <div role="radiogroup" aria-label="Group usage by" className="flex flex-wrap gap-2">
        {(['day', 'user', 'school', 'provider'] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={group === value}
            onClick={() => setGroup(value)}
            className={cn(
              'min-h-11 rounded-full border px-4 text-sm font-medium capitalize',
              group === value && 'border-primary bg-secondary text-secondary-foreground',
            )}
          >
            By {value === 'provider' ? 'model' : value}
          </button>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        Last 30 days. Estimated cost of priced calls: <strong>{usd.format(total)}</strong>
        {priced.length < rows.length && ' (some models have no price set, so their cost is unknown)'}
      </p>
      {usage.isPending ? (
        <Loading />
      ) : rows.length === 0 ? (
        <Empty>No AI calls in this period.</Empty>
      ) : (
        <Table head={[group === 'provider' ? 'Model' : group, 'Calls', 'Tokens in', 'Tokens out', 'Est. cost']}>
          {rows.map((row) => (
            <tr key={row.key}>
              <td className="max-w-56 truncate">{row.label}</td>
              <td className="tabular-nums">{row.calls}</td>
              <td className="tabular-nums">{row.input_tokens.toLocaleString()}</td>
              <td className="tabular-nums">{row.output_tokens.toLocaleString()}</td>
              <td className="tabular-nums">{row.cost_usd === null ? 'unknown' : usd.format(Number(row.cost_usd))}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  )
}

function UsersTab() {
  const [search, setSearch] = useState('')
  const users = useQuery(adminQueries.users(useDebouncedValue(search.trim(), 250)))
  const setActive = useAdminAction(adminActions.setUserActive)
  return (
    <div className="grid gap-4">
      <Input
        type="search"
        aria-label="Search users"
        placeholder="Search by name or email"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className={CONTROL_CLASS}
      />
      {users.isPending ? (
        <Loading />
      ) : (
        <Table head={['Name', 'Email', 'Role', 'Status', '']}>
          {users.data?.map((user) => (
            <tr key={user.id}>
              <td>{user.full_name}</td>
              <td>{user.email}</td>
              <td className="capitalize">{user.role.replace('_', ' ')}</td>
              <td>{!user.is_active ? 'Deactivated' : user.is_verified ? 'Active' : 'Unverified'}</td>
              <td>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={setActive.isPending}
                  onClick={() => setActive.mutate({ id: user.id, active: !user.is_active }, { onError: fail })}
                >
                  {user.is_active ? 'Deactivate' : 'Reactivate'}
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  )
}

function MentorsTab() {
  const mentors = useQuery(adminQueries.mentors)
  const approve = useAdminAction(adminActions.approveMentor)
  if (mentors.isPending) return <Loading />
  if (mentors.data?.length === 0) return <Empty>No mentors have signed up yet.</Empty>
  return (
    <ul className="grid gap-3">
      {mentors.data?.map(({ user, profile }) => (
        <li key={user.id} className="rounded-2xl border bg-card p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-semibold">{user.full_name}</p>
              <p className="text-sm text-muted-foreground">
                {[user.email, profile.organisation].filter(Boolean).join(' · ')}
              </p>
              <p className="mt-2 text-sm">
                {profile.expertise.map((type) => HELP_TYPES[type as HelpType] ?? type).join(', ') || 'No expertise listed'}
                {' · '}
                {profile.regions.join(', ') || 'No region'}
              </p>
              {profile.offers && <p className="mt-1 text-sm text-muted-foreground">{profile.offers}</p>}
            </div>
            <Button
              variant={profile.is_approved ? 'outline' : 'default'}
              size="touch"
              disabled={approve.isPending}
              onClick={() => approve.mutate({ id: user.id, approved: !profile.is_approved }, { onError: fail })}
            >
              {profile.is_approved ? 'Withdraw approval' : 'Approve'}
            </Button>
          </div>
        </li>
      ))}
    </ul>
  )
}

function RequestsTab() {
  const requests = useQuery(adminQueries.requests)
  const mentors = useQuery(adminQueries.mentors)
  const assign = useAdminAction(adminActions.assignMentor)
  const approved = mentors.data?.filter((mentor) => mentor.profile.is_approved) ?? []
  if (requests.isPending) return <Loading />
  if (requests.data?.length === 0) return <Empty>No mentor requests yet.</Empty>
  return (
    <Table head={['Project', 'Learner', 'Needs', 'Status', 'Mentor']}>
      {requests.data?.map((request) => (
        <tr key={request.id}>
          <td>{request.project_title}</td>
          <td>{[request.learner.first_name, request.school_name, request.province].filter(Boolean).join(', ')}</td>
          <td>{request.help_types.map((type) => HELP_TYPES[type as HelpType] ?? type).join(', ')}</td>
          <td>{STATUS_LABELS[request.status]}</td>
          <td>
            {request.status === 'pending' ? (
              <select
                aria-label={`Assign a mentor to ${request.project_title}`}
                defaultValue=""
                disabled={assign.isPending}
                onChange={(event) =>
                  event.target.value &&
                  assign.mutate({ requestId: request.id, mentorId: event.target.value }, { onError: fail })
                }
                className="h-9 rounded-lg border border-input bg-transparent px-2"
              >
                <option value="">Assign…</option>
                {approved.map((mentor) => (
                  <option key={mentor.user.id} value={mentor.user.id}>
                    {mentor.user.full_name}
                  </option>
                ))}
              </select>
            ) : (
              (request.mentor?.first_name ?? '—')
            )}
          </td>
        </tr>
      ))}
    </Table>
  )
}

function SchoolsTab() {
  const schools = useQuery(adminQueries.schools)
  const verify = useAdminAction(adminActions.verifySchool)
  if (schools.isPending) return <Loading />
  return (
    <Table head={['School', 'Where', 'Learners', 'Verified', '']}>
      {schools.data?.map((school) => (
        <tr key={school.id}>
          <td>{school.name}</td>
          <td>{[school.town, school.province].filter(Boolean).join(', ')}</td>
          <td className="tabular-nums">{school.learners}</td>
          <td>{school.is_verified ? 'Yes' : 'Added by a learner'}</td>
          <td>
            <Button
              variant="outline"
              size="sm"
              disabled={verify.isPending}
              onClick={() => verify.mutate({ id: school.id, verified: !school.is_verified }, { onError: fail })}
            >
              {school.is_verified ? 'Unverify' : 'Verify'}
            </Button>
          </td>
        </tr>
      ))}
    </Table>
  )
}

const DIRECTIONS: Record<string, string> = {
  input: 'Learner to AI mentor',
  output: 'AI mentor reply',
  mentor_chat: 'Learner and human mentor',
}

function ModerationTab() {
  const flags = useQuery(adminQueries.flags)
  const review = useAdminAction(adminActions.reviewFlag)
  if (flags.isPending) return <Loading />
  if (flags.data?.length === 0) return <Empty>Nothing waiting for review.</Empty>
  return (
    <ul className="grid gap-3">
      {flags.data?.map((flag) => (
        <li key={flag.id} className="rounded-2xl border bg-card p-4">
          <p className="text-sm text-muted-foreground">
            {DIRECTIONS[flag.direction] ?? flag.direction} · {new Date(flag.created_at).toLocaleString()} ·{' '}
            {flag.checked ? flag.categories.join(', ') || 'flagged' : 'blocked because the safety check failed'}
          </p>
          <p className="mt-2 whitespace-pre-wrap [overflow-wrap:anywhere]">{flag.content}</p>
          <Button
            variant="outline"
            size="touch"
            className="mt-3"
            disabled={review.isPending}
            onClick={() => review.mutate(flag.id, { onError: fail })}
          >
            Mark as reviewed
          </Button>
        </li>
      ))}
    </ul>
  )
}

function ProvidersTab() {
  const providers = useQuery(adminQueries.providers)
  if (providers.isPending) return <Loading />
  return (
    <Table head={['Provider', 'In use', 'Model', 'Health']}>
      {providers.data?.map((provider) => (
        <tr key={provider.name}>
          <td className="capitalize">{provider.name}</td>
          <td>{provider.active ? 'Yes' : ''}</td>
          <td>{provider.model ?? '—'}</td>
          <td className={provider.healthy ? 'text-success' : 'text-muted-foreground'}>
            {provider.healthy ? 'Working' : (provider.detail ?? 'Not checked')}
          </td>
        </tr>
      ))}
    </Table>
  )
}

function StageEditor({ stage }: { stage: Schemas['StageDefinitionOut'] }) {
  const queryClient = useQueryClient()
  const [instructions, setInstructions] = useState(stage.instructions)
  const [goal, setGoal] = useState(stage.goal)
  const save = useAdminAction(async () =>
    unwrap(
      await api.PUT('/api/v1/admin/stages/{key}', {
        params: { path: { key: stage.key } },
        body: {
          title: stage.title,
          goal,
          deliverables: stage.deliverables,
          exit_criteria: stage.exit_criteria,
          instructions,
        },
      }),
    ),
  )
  const dirty = instructions !== stage.instructions || goal !== stage.goal
  return (
    <details className="rounded-2xl border bg-card p-4">
      <summary className="cursor-pointer font-semibold">
        {stage.position}. {stage.title}
        <span className="ml-2 text-sm font-normal text-muted-foreground">version {stage.version}</span>
      </summary>
      <div className="mt-4 grid gap-3">
        <label className="grid gap-1.5 text-sm font-medium">
          Goal shown to learners
          <textarea
            value={goal}
            rows={2}
            onChange={(event) => setGoal(event.target.value)}
            className="rounded-xl border border-input bg-transparent px-3 py-2 text-base font-normal"
          />
        </label>
        <label className="grid gap-1.5 text-sm font-medium">
          Instructions to the AI mentor in this stage
          <textarea
            value={instructions}
            rows={10}
            onChange={(event) => setInstructions(event.target.value)}
            className="rounded-xl border border-input bg-transparent px-3 py-2 font-mono text-sm font-normal"
          />
        </label>
        <p className="text-sm text-muted-foreground">
          Checklist: {stage.deliverables.map((item) => item.label).join(' · ')}
        </p>
        <Button
          size="touch"
          className="justify-self-start"
          disabled={!dirty || save.isPending}
          onClick={() =>
            save.mutate(undefined, {
              onError: fail,
              onSuccess: () => {
                toast.success('Stage updated. It applies from the next message.')
                void queryClient.invalidateQueries({ queryKey: ['admin', 'stages'] })
              },
            })
          }
        >
          {save.isPending ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
    </details>
  )
}

function StagesTab() {
  const stages = useQuery(adminQueries.stages)
  if (stages.isPending) return <Loading />
  return (
    <div className="grid gap-3">
      {stages.data?.map((stage) => (
        <StageEditor key={`${stage.key}-${stage.version}`} stage={stage} />
      ))}
    </div>
  )
}

const PANELS: Record<Tab, () => ReactNode> = {
  Usage: UsageTab,
  Users: UsersTab,
  Mentors: MentorsTab,
  Requests: RequestsTab,
  Schools: SchoolsTab,
  Moderation: ModerationTab,
  AI: ProvidersTab,
  Stages: StagesTab,
}

function AdminPage() {
  const [tab, setTab] = useState<Tab>('Usage')
  const Panel = PANELS[tab]
  return (
    <>
      <h1 className="text-3xl font-semibold">Admin</h1>
      <div
        role="tablist"
        aria-label="Admin sections"
        className="-mx-4 mt-6 flex gap-1 overflow-x-auto px-4 [scrollbar-width:none] md:mx-0 md:flex-wrap md:px-0"
      >
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={cn(
              'min-h-11 shrink-0 rounded-full px-4 text-sm font-medium',
              tab === name ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {name}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={tab} className="mt-6">
        <Panel />
      </div>
    </>
  )
}
