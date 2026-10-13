import { createFileRoute, Link } from '@tanstack/react-router'
import { LightbulbIcon } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/empty-state'
import { Button } from '@/components/ui/button'
import { useUser } from '@/features/auth/api'

export const Route = createFileRoute('/app/')({ component: DashboardPage })

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

  return (
    <>
      <h1 className="text-3xl font-semibold">
        {greeting(hour)}, {firstName}
      </h1>
      <p className="mt-1 text-muted-foreground">Ready to build something for the expo?</p>

      <div className="mt-8">
        <EmptyState
          icon={LightbulbIcon}
          title="Every project starts with a problem"
          action={
            <Button asChild size="touch">
              <Link to="/app/projects">Go to projects</Link>
            </Button>
          }
        >
          Your mentor will help you spot one worth solving in your community, school or home.
        </EmptyState>
      </div>
    </>
  )
}
