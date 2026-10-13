import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { Logo } from '@/components/brand/logo'
import { ThemeToggle } from '@/components/theme-toggle'
import { PATHWAY_STAGES } from '@/features/pathway/stages'

interface AuthShellProps {
  title: string
  subtitle?: ReactNode
  children: ReactNode
  footer?: ReactNode
}

/**
 * The frame for sign-in pages. On phones it is just the form; from `lg` up a
 * brand panel sits beside it, showing the pathway the learner is signing up for.
 */
export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden overflow-hidden bg-primary text-primary-foreground lg:block">
        <div aria-hidden="true" className="bg-grid absolute inset-0 opacity-60 invert dark:invert-0" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <p className="max-w-sm font-heading text-3xl leading-tight font-semibold">
            From an idea on paper to a project on the expo floor.
          </p>
          <ol className="grid gap-2.5">
            {PATHWAY_STAGES.map((stage, index) => (
              <li key={stage.title} className="flex items-center gap-3 text-sm">
                <span
                  aria-hidden="true"
                  className="grid size-6 place-items-center rounded-full bg-primary-foreground/15 text-xs font-semibold"
                >
                  {index + 1}
                </span>
                {stage.title}
              </li>
            ))}
          </ol>
        </div>
      </aside>

      <div className="flex min-h-dvh flex-col pt-safe">
        <header className="flex h-16 items-center justify-between px-safe sm:px-8">
          <Link to="/" aria-label="Mentor Pilot home" className="rounded-lg">
            <Logo />
          </Link>
          <ThemeToggle />
        </header>
        <main id="main" className="flex flex-1 flex-col px-safe pt-6 pb-10 sm:justify-center sm:px-8">
          <div className="mx-auto w-full max-w-sm">
            <h1 className="text-3xl font-semibold">{title}</h1>
            {subtitle && <p className="mt-2 text-muted-foreground">{subtitle}</p>}
            <div className="mt-8">{children}</div>
            {footer && <div className="mt-8 text-sm text-muted-foreground">{footer}</div>}
          </div>
        </main>
      </div>
    </div>
  )
}

/** Inline text links inside the sign-in pages. */
export const linkClass = 'font-medium text-primary underline-offset-4 hover:underline'
