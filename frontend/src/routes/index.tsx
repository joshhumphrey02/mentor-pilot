import { createFileRoute, Link } from '@tanstack/react-router'
import { ArrowRightIcon } from 'lucide-react'
import { motion, MotionConfig } from 'motion/react'
import type { ReactNode } from 'react'

import { FlipWords } from '@/components/aceternity/flip-words'
import { FloatingNavbar } from '@/components/aceternity/floating-navbar'
import { type FocusCard, FocusCards } from '@/components/aceternity/focus-cards'
import { ImagesSlider } from '@/components/aceternity/images-slider'
import { CircuitBlock } from '@/components/blocks/circuit-block'
import { Logo } from '@/components/brand/logo'
import { Photo } from '@/components/photo'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/api'
import { LED_CIRCUIT } from '@/features/circuit/examples'
import { PathwayCarousel } from '@/features/landing/pathway-carousel'
import { Reveal } from '@/features/landing/reveal'
import { WhenVisible } from '@/features/landing/when-visible'
import { PHOTOGRAPHERS, PHOTOS } from '@/lib/photos'

export const Route = createFileRoute('/')({ component: LandingPage })

const HERO_PHOTOS = [PHOTOS.makerspace, PHOTOS.teamBuild, PHOTOS.breadboardHands, PHOTOS.classroomReader]
const HERO_WORDS = ['designed.', 'built.', 'tested.', 'expo-ready.']

const AUDIENCES: FocusCard[] = [
  {
    title: 'Learners',
    caption: 'Start with curiosity. Finish with a project you can defend.',
    photo: PHOTOS.learnerNotes,
    to: '/register',
    action: 'Get started',
  },
  {
    title: 'Schools',
    caption: 'An expo mentor for every learner, lab or no lab.',
    photo: PHOTOS.classroom,
  },
  {
    title: 'Mentors',
    caption: 'Meet learners who arrive with a design and a plan.',
    photo: PHOTOS.mentoring,
    to: '/register-mentor',
    action: 'Become a mentor',
  },
]

function SectionHeading({ id, eyebrow, children }: { id: string; eyebrow: string; children: ReactNode }) {
  return (
    <Reveal className="mx-auto max-w-6xl px-safe">
      <p className="text-sm font-semibold tracking-wide text-primary uppercase">{eyebrow}</p>
      <h2 id={id} className="mt-2 text-3xl font-semibold sm:text-5xl">
        {children}
      </h2>
    </Reveal>
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
    // Every animation on the page stands down for visitors who prefer less motion.
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col">
        <FloatingNavbar>
          {(floating) => (
            <>
              <Logo />
              <div className="flex items-center gap-1">
                <ThemeToggle />
                {!user && (
                  <Button asChild variant="ghost" size="touch" className="px-3">
                    <Link to="/login">Log in</Link>
                  </Button>
                )}
                {floating && (
                  <Button asChild size="touch" className="hidden rounded-full sm:inline-flex">
                    {start}
                  </Button>
                )}
              </div>
            </>
          )}
        </FloatingNavbar>

        <main id="main" className="flex-1">
          <ImagesSlider photos={HERO_PHOTOS}>
            <div className="mx-auto flex min-h-[92svh] max-w-6xl flex-col justify-end px-safe pt-28 pb-16 text-white sm:pb-24">
              <motion.div
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, ease: 'easeOut' }}
              >
                <p className="inline-flex rounded-full border border-white/25 bg-white/10 px-3 py-1.5 text-sm font-medium backdrop-blur-sm">
                  AI mentor for science and engineering expos
                </p>
                <h1 className="mt-5 text-5xl leading-[1.02] font-semibold sm:text-7xl">
                  <span className="sr-only">Your idea, expo-ready.</span>
                  <span aria-hidden="true" className="block">
                    Your idea,
                  </span>
                  <FlipWords words={HERO_WORDS} className="text-spark" />
                </h1>
                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <Button asChild size="touch" className="rounded-full sm:px-6">
                    {start}
                  </Button>
                  <Button
                    asChild
                    variant="outline"
                    size="touch"
                    className="rounded-full border-white/35 bg-white/10 text-white backdrop-blur-sm hover:bg-white/20 hover:text-white sm:px-6 dark:border-white/35 dark:bg-white/10 dark:hover:bg-white/20"
                  >
                    <a href="#demo">Try the breadboard</a>
                  </Button>
                </div>
              </motion.div>
            </div>
          </ImagesSlider>

          <section aria-labelledby="pathway-heading" className="py-16 sm:py-24">
            <SectionHeading id="pathway-heading" eyebrow="The pathway">
              Nine stages. One finished project.
            </SectionHeading>
            <div className="mt-8 sm:mt-12">
              <PathwayCarousel />
            </div>
          </section>

          <section
            id="demo"
            aria-labelledby="demo-heading"
            className="relative scroll-mt-20 border-y bg-card py-16 sm:py-24"
          >
            <div
              aria-hidden="true"
              className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]"
            />
            <div className="relative">
              <SectionHeading id="demo-heading" eyebrow="Show, don't tell">
                Ask how to wire an LED. Get this.
              </SectionHeading>
              <Reveal className="mx-auto mt-8 max-w-2xl px-safe sm:mt-12">
                <WhenVisible minHeight={520}>
                  <CircuitBlock block={LED_CIRCUIT} photos={false} />
                </WhenVisible>
              </Reveal>
            </div>
          </section>

          <section aria-labelledby="who-heading" className="py-16 sm:py-24">
            <SectionHeading id="who-heading" eyebrow="Who it's for">
              Learners, schools and mentors.
            </SectionHeading>
            <Reveal className="mx-auto mt-8 max-w-6xl px-safe sm:mt-12">
              <FocusCards cards={AUDIENCES} />
            </Reveal>
          </section>

          <section aria-labelledby="start-heading" className="px-safe pb-16 sm:pb-24">
            <Reveal className="relative isolate mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-neutral-950 px-6 py-16 text-center text-white sm:py-24">
              <Photo
                photo={PHOTOS.breadboardDark}
                sizes="(min-width: 1152px) 1152px, 100vw"
                decorative
                className="absolute inset-0 -z-20"
              />
              <div aria-hidden="true" className="absolute inset-0 -z-10 bg-neutral-950/65" />
              <h2 id="start-heading" className="mx-auto max-w-xl text-3xl font-semibold sm:text-5xl">
                It starts with one question.
              </h2>
              <Button asChild size="touch" className="mt-8 rounded-full sm:px-6">
                {start}
              </Button>
            </Reveal>
          </section>
        </main>

        <footer className="border-t pb-safe">
          <div className="mx-auto max-w-6xl px-safe py-6 text-sm text-muted-foreground">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p>Built for learners in the Western Cape, South Africa.</p>
              <Link to="/privacy" className="underline-offset-4 hover:underline">
                Privacy notice
              </Link>
            </div>
            <p className="mt-3 text-xs">
              Photos by {PHOTOGRAPHERS.join(', ')} on{' '}
              <a
                href="https://unsplash.com"
                target="_blank"
                rel="noreferrer"
                className="underline underline-offset-4"
              >
                Unsplash
              </a>
              .
            </p>
          </div>
        </footer>
      </div>
    </MotionConfig>
  )
}
