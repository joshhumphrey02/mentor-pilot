import { createFileRoute, Link } from '@tanstack/react-router'
import {
  ArrowRightIcon,
  BrainIcon,
  EyeIcon,
  GraduationCapIcon,
  HandshakeIcon,
  type LucideIcon,
  RouteIcon,
  SchoolIcon,
  WrenchIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { CircuitBlock } from '@/components/blocks/circuit-block'
import { Logo } from '@/components/brand/logo'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/api'
import { LED_CIRCUIT } from '@/features/circuit/examples'
import { PathwayWalkthrough } from '@/features/landing/pathway-walkthrough'
import { WhenVisible } from '@/features/landing/when-visible'

export const Route = createFileRoute('/')({ component: LandingPage })

const DIFFERENCES: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: RouteIcon,
    title: 'A pathway, not a chat box',
    text: 'Every project moves through nine stages. Your mentor always knows where you are and what comes next.',
  },
  {
    icon: EyeIcon,
    title: 'It shows you',
    text: 'Interactive breadboards, diagrams, real photos, charts of your own data. Not walls of text.',
  },
  {
    icon: BrainIcon,
    title: 'Your thinking stays yours',
    text: 'It asks questions, gives options and honest feedback. It will not write your project for you, because judges can tell.',
  },
  {
    icon: HandshakeIcon,
    title: 'Real people when it counts',
    text: 'When it is time to build, it connects you with a vetted human mentor near you.',
  },
]

const AUDIENCES: { icon: LucideIcon; who: string; text: string; cta?: ReactNode }[] = [
  {
    icon: GraduationCapIcon,
    who: 'For learners',
    text: 'Start with nothing but curiosity. Finish with a project you understand and can defend in front of a judge.',
  },
  {
    icon: SchoolIcon,
    who: 'For schools',
    text: 'Give every learner an experienced expo mentor, even without a lab or a specialist teacher. Pay only for what is used.',
  },
  {
    icon: WrenchIcon,
    who: 'For mentors',
    text: 'Meet learners who arrive with a design, a materials list and a plan, ready for your hands-on help.',
    cta: (
      <Link
        to="/register-mentor"
        className="mt-3 inline-flex min-h-11 items-center gap-1.5 font-medium text-primary underline-offset-4 hover:underline"
      >
        Become a mentor
        <ArrowRightIcon aria-hidden="true" className="size-4" />
      </Link>
    ),
  },
]

function Section({
  id,
  eyebrow,
  title,
  lead,
  children,
}: {
  id: string
  eyebrow: string
  title: string
  lead?: string
  children: ReactNode
}) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="scroll-mt-6 border-t">
      <div className="mx-auto max-w-5xl px-safe py-14 sm:py-20">
        <p className="text-sm font-semibold tracking-wide text-primary uppercase">{eyebrow}</p>
        <h2 id={`${id}-heading`} className="mt-2 max-w-2xl text-3xl font-semibold sm:text-4xl">
          {title}
        </h2>
        {lead && <p className="mt-3 max-w-xl text-muted-foreground">{lead}</p>}
        <div className="mt-10">{children}</div>
      </div>
    </section>
  )
}

function LandingPage() {
  const { data: user } = useMe()
  const start = user ? (
    <Link to="/app">
      Open your workspace
      <ArrowRightIcon data-icon="inline-end" />
    </Link>
  ) : (
    <Link to="/register">
      Start your project
      <ArrowRightIcon data-icon="inline-end" />
    </Link>
  )

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
            <p className="inline-flex rounded-full border bg-card px-3 py-1.5 text-sm font-medium">
              An AI mentor for science and engineering expos
            </p>
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
              Mentor Pilot guides you step by step: finding a real problem, designing your
              experiment, testing it, and getting ready for the judges. When it's time to build,
              it connects you with a human mentor.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="touch">
                {start}
              </Button>
              <Button asChild variant="outline" size="touch">
                <a href="#demo">Try the breadboard</a>
              </Button>
            </div>
          </div>
        </section>

        <Section
          id="demo"
          eyebrow="Show, don't tell"
          title="Ask how to wire an LED. Get this."
          lead="Not a paragraph: a breadboard you can explore. Reveal the metal inside, step through the build, and see the mistake almost everyone makes first."
        >
          <div className="mx-auto max-w-2xl">
            <WhenVisible minHeight={520}>
              <CircuitBlock block={LED_CIRCUIT} photos={false} />
            </WhenVisible>
          </div>
        </Section>

        <Section
          id="pathway"
          eyebrow="The pathway"
          title="Nine stages. One finished project."
          lead="The same route experienced expo mentors use, so you are never left wondering what to do next."
        >
          <div className="mx-auto max-w-2xl">
            <PathwayWalkthrough />
          </div>
        </Section>

        <Section id="why" eyebrow="Why not just a chatbot?" title="Built to mentor, not to answer.">
          <ul className="grid gap-4 sm:grid-cols-2">
            {DIFFERENCES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="rounded-2xl border bg-card p-5 shadow-soft">
                <span className="grid size-11 place-items-center rounded-xl bg-secondary text-secondary-foreground">
                  <Icon aria-hidden="true" className="size-5" />
                </span>
                <h3 className="mt-4 text-lg font-semibold">{title}</h3>
                <p className="mt-1.5 text-muted-foreground">{text}</p>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="who" eyebrow="Who it's for" title="Learners, schools and mentors.">
          <ul className="grid gap-4 md:grid-cols-3">
            {AUDIENCES.map(({ icon: Icon, who, text, cta }) => (
              <li key={who} className="rounded-2xl border bg-card p-5 shadow-soft">
                <Icon aria-hidden="true" className="size-6 text-primary" />
                <h3 className="mt-3 text-lg font-semibold">{who}</h3>
                <p className="mt-1.5 text-muted-foreground">{text}</p>
                {cta}
              </li>
            ))}
          </ul>
        </Section>

        <section className="border-t bg-primary text-primary-foreground">
          <div className="mx-auto max-w-5xl px-safe py-14 text-center sm:py-20">
            <h2 className="mx-auto max-w-xl text-3xl font-semibold sm:text-4xl">
              Your project starts with one question.
            </h2>
            <p className="mx-auto mt-3 max-w-md opacity-90">
              What have you noticed around you that could be better?
            </p>
            <Button
              asChild
              size="touch"
              className="mt-8 bg-primary-foreground text-primary hover:bg-primary-foreground/90"
            >
              {start}
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t pb-safe">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-safe py-6 text-sm text-muted-foreground">
          <p>Built for learners in the Western Cape, South Africa.</p>
          <Link to="/privacy" className="underline-offset-4 hover:underline">
            Privacy notice
          </Link>
        </div>
      </footer>
    </div>
  )
}
