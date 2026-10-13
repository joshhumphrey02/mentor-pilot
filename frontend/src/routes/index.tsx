import { createFileRoute, Link } from '@tanstack/react-router'
import { ArrowRightIcon } from 'lucide-react'

import { Logo } from '@/components/brand/logo'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/api'
import { PATHWAY_STAGES } from '@/features/pathway/stages'
import { SystemStatus } from '@/features/system/system-status'

export const Route = createFileRoute('/')({ component: HomePage })

// Stage 6 is where the AI hands the learner to a human mentor.
const HANDOFF_STAGE = 6

function HomePage() {
  const { data: user } = useMe()

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="pt-safe">
        <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-safe">
          <Logo />
          <div className="flex items-center gap-1">
            <ThemeToggle />
            {!user && (
              <Button asChild variant="ghost" size="touch" className="px-3">
                <Link to="/login">Log in</Link>
              </Button>
            )}
          </div>
        </div>
      </header>

      <main id="main" className="flex-1">
        <section className="relative overflow-hidden">
          <div
            aria-hidden="true"
            className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]"
          />
          <div className="relative mx-auto max-w-5xl px-safe pt-10 pb-14 sm:pt-20 sm:pb-24">
            <SystemStatus />
            <h1 className="mt-6 max-w-3xl text-4xl leading-[1.05] font-semibold sm:text-6xl">
              From an idea on paper to a project on the{' '}
              <span className="relative whitespace-nowrap">
                expo floor
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 -bottom-1 h-2 rounded-full bg-spark/70 sm:h-3"
                />
              </span>
              .
            </h1>
            <p className="mt-5 max-w-xl text-lg text-muted-foreground">
              Mentor Pilot is an AI STEM mentor that guides you step by step: finding a real
              problem, designing your experiment, testing it, and getting ready for the judges.
              When it's time to build, it connects you with a human mentor.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="touch">
                {user ? (
                  <Link to="/app">
                    Open your workspace
                    <ArrowRightIcon data-icon="inline-end" />
                  </Link>
                ) : (
                  <Link to="/register">
                    Start your project
                    <ArrowRightIcon data-icon="inline-end" />
                  </Link>
                )}
              </Button>
              <Button asChild variant="outline" size="touch">
                <a href="#pathway">See the pathway</a>
              </Button>
            </div>
          </div>
        </section>

        <section id="pathway" aria-labelledby="pathway-heading" className="scroll-mt-6 border-t">
          <div className="mx-auto max-w-5xl px-safe py-14 sm:py-20">
            <p className="text-sm font-semibold tracking-wide text-primary uppercase">
              The pathway
            </p>
            <h2 id="pathway-heading" className="mt-2 text-3xl font-semibold sm:text-4xl">
              Nine stages. One finished project.
            </h2>
            <p className="mt-3 max-w-xl text-muted-foreground">
              Every project follows the same route experienced expo mentors use. Your mentor
              always knows where you are and what comes next.
            </p>

            <ol className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {PATHWAY_STAGES.map((stage, index) => {
                const number = index + 1
                return (
                  <li
                    key={stage.title}
                    className="flex gap-4 rounded-2xl border bg-card p-4 shadow-soft"
                  >
                    <span
                      aria-hidden="true"
                      className="grid size-10 shrink-0 place-items-center rounded-xl bg-secondary font-heading text-lg font-semibold text-secondary-foreground"
                    >
                      {number}
                    </span>
                    <div className="min-w-0">
                      <h3 className="font-sans text-base font-semibold tracking-normal">
                        <span className="sr-only">Stage {number}: </span>
                        {stage.title}
                      </h3>
                      <p className="mt-1 text-sm text-muted-foreground">{stage.summary}</p>
                      {number === HANDOFF_STAGE && (
                        <p className="mt-2 inline-flex rounded-full bg-spark px-2.5 py-0.5 text-xs font-semibold text-spark-foreground">
                          Human mentor joins here
                        </p>
                      )}
                    </div>
                  </li>
                )
              })}
            </ol>
          </div>
        </section>
      </main>

      <footer className="border-t pb-safe">
        <div className="mx-auto max-w-5xl px-safe py-6 text-sm text-muted-foreground">
          <p>Built for learners in the Western Cape, South Africa.</p>
          <Link to="/privacy" className="mt-1 inline-block underline-offset-4 hover:underline">
            Privacy notice
          </Link>
        </div>
      </footer>
    </div>
  )
}
