import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  children: ReactNode
  action?: ReactNode
}

/** What a screen shows before there is anything in it: why, and what to do next. */
export function EmptyState({ icon: Icon, title, children, action }: EmptyStateProps) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-dashed px-6 py-10 text-center">
      <div
        aria-hidden="true"
        className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]"
      />
      <div className="relative mx-auto max-w-sm">
        <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-secondary text-secondary-foreground">
          <Icon aria-hidden="true" className="size-6" />
        </span>
        <h2 className="mt-4 text-xl font-semibold">{title}</h2>
        <p className="mt-2 text-muted-foreground">{children}</p>
        {action && <div className="mt-6">{action}</div>}
      </div>
    </div>
  )
}
