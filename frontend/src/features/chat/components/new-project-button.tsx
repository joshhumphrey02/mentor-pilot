import { useNavigate } from '@tanstack/react-router'
import { PlusIcon } from 'lucide-react'
import type { ComponentProps } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api/errors'

import { useCreateProject } from '../api'

/**
 * One tap to a new project and straight into the chat. There is no form to
 * fill in first: the mentor's opening questions are how a project gets shaped,
 * and it is named once the learner has chosen an idea.
 */
export function NewProjectButton(props: ComponentProps<typeof Button>) {
  const navigate = useNavigate()
  const create = useCreateProject()

  return (
    <Button
      size="touch"
      disabled={create.isPending}
      onClick={async () => {
        try {
          const project = await create.mutateAsync('')
          await navigate({ to: '/project/$projectId', params: { projectId: project.id } })
        } catch (error) {
          toast.error(errorMessage(error))
        }
      }}
      {...props}
    >
      <PlusIcon data-icon="inline-start" />
      {create.isPending ? 'Starting…' : 'Start a new project'}
    </Button>
  )
}
