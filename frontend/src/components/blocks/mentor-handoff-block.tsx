import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { HandshakeIcon } from 'lucide-react'
import { useState } from 'react'

import { FormAlert } from '@/components/form/fields'
import { ResponsiveDialog } from '@/components/responsive-dialog'
import { Button } from '@/components/ui/button'
import { useWorkspace } from '@/features/chat/workspace-context'
import {
  HELP_TYPES,
  type HelpType,
  myRequestsQueryOptions,
  STATUS_LABELS,
  useRequestMentor,
} from '@/features/mentoring/api'
import { HelpTypePicker } from '@/features/mentoring/help-type-picker'
import type { Schemas } from '@/lib/api/client'
import { errorMessage } from '@/lib/api/errors'

const MIN_DESCRIPTION = 10

/**
 * The mentor's offer of a human mentor. The request is the learner's to send:
 * they choose what help they want and describe it in their own words.
 */
export function MentorHandoffBlock({ block }: { block: Schemas['MentorHandoffBlock'] }) {
  const workspace = useWorkspace()
  const requests = useQuery({ ...myRequestsQueryOptions, enabled: workspace !== null })
  const send = useRequestMentor(workspace?.projectId ?? '')
  const [open, setOpen] = useState(false)
  const [helpTypes, setHelpTypes] = useState<HelpType[]>(block.help_types)
  const [description, setDescription] = useState('')
  if (!workspace) return null

  const existing = requests.data?.find(
    (request) =>
      request.project_id === workspace.projectId &&
      request.status !== 'cancelled' &&
      request.status !== 'completed',
  )
  const ready = helpTypes.length > 0 && description.trim().length >= MIN_DESCRIPTION

  return (
    <section
      aria-label="Get help from a human mentor"
      className="rounded-2xl border-2 border-spark/60 bg-warning-soft p-5"
    >
      <h3 className="flex items-center gap-2 font-heading text-lg font-semibold">
        <HandshakeIcon aria-hidden="true" className="size-5 text-warning" />
        Time for a human mentor
      </h3>
      <p className="mt-1">{block.reason}</p>
      <ul aria-label="Help suggested" className="mt-3 flex flex-wrap gap-1.5">
        {block.help_types.map((type) => (
          <li key={type} className="rounded-full bg-background px-2.5 py-0.5 text-sm">
            {HELP_TYPES[type]}
          </li>
        ))}
      </ul>

      {existing ? (
        <p role="status" className="mt-4 rounded-xl bg-background p-3 text-sm">
          <span className="font-semibold">{STATUS_LABELS[existing.status]}.</span> You can follow
          your request and talk to your mentor in the{' '}
          <Link to="/app/mentor" className="font-medium text-primary underline underline-offset-4">
            Mentor tab
          </Link>
          .
        </p>
      ) : (
        <Button size="touch" className="mt-4" onClick={() => setOpen(true)}>
          Request a mentor
        </Button>
      )}

      <ResponsiveDialog
        open={open}
        onOpenChange={setOpen}
        title="Request a human mentor"
        description="A vetted mentor near you will see this, along with your project's title, stage and idea. They only see your first name."
      >
        <form
          className="grid gap-4"
          onSubmit={async (event) => {
            event.preventDefault()
            if (!ready) return
            const created = await send
              .mutateAsync({ help_types: helpTypes, description: description.trim() })
              .catch(() => null)
            if (created) setOpen(false)
          }}
        >
          {send.error && <FormAlert>{errorMessage(send.error)}</FormAlert>}
          <HelpTypePicker
            legend="What do you need help with?"
            value={helpTypes}
            onChange={setHelpTypes}
          />
          <div className="grid gap-1.5">
            <label htmlFor="mentor-request-description" className="text-sm font-medium">
              Tell the mentor what you're stuck on
            </label>
            <textarea
              id="mentor-request-description"
              value={description}
              rows={4}
              maxLength={2000}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="For example: I've designed my circuit but I've never soldered before."
              className="min-h-24 rounded-xl border border-input bg-transparent px-3.5 py-2.5 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </div>
          <Button type="submit" size="touch" disabled={!ready || send.isPending}>
            {send.isPending ? 'Sending…' : 'Send request'}
          </Button>
        </form>
      </ResponsiveDialog>
    </section>
  )
}
