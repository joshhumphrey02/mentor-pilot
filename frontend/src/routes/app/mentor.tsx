import { createFileRoute } from '@tanstack/react-router'
import { UsersRoundIcon } from 'lucide-react'

import { EmptyState } from '@/components/empty-state'

export const Route = createFileRoute('/app/mentor')({ component: MentorPage })

function MentorPage() {
  return (
    <>
      <h1 className="text-3xl font-semibold">Human mentors</h1>
      <div className="mt-8">
        <EmptyState icon={UsersRoundIcon} title="No mentor requests yet">
          When your project is ready to build, you can ask for a human mentor to help with
          hardware, lab access or materials. Your requests will show up here.
        </EmptyState>
      </div>
    </>
  )
}
