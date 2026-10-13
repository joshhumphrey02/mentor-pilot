import { Link } from '@tanstack/react-router'
import { motion, MotionConfig } from 'motion/react'
import type { ReactNode } from 'react'

import { SpotlightCard } from '@/components/aceternity/spotlight-card'
import { Logo } from '@/components/brand/logo'
import { Photo } from '@/components/photo'
import { ThemeToggle } from '@/components/theme-toggle'
import { type Photo as PhotoData, PHOTOS } from '@/lib/photos'

interface AuthShellProps {
  title: string
  subtitle?: ReactNode
  children: ReactNode
  footer?: ReactNode
  /** The picture beside the form. */
  photo?: PhotoData
  /** One line over the picture, shown from `lg` up. */
  tagline?: string
}

/**
 * The frame for sign-in pages: a photo and the form. On phones the photo is a
 * banner the form slides up over; from `lg` up they sit side by side.
 */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  photo = PHOTOS.arduino,
  tagline = 'Your idea, expo-ready.',
}: AuthShellProps) {
  return (
    <MotionConfig reducedMotion="user">
      <div className="grid min-h-dvh grid-rows-[auto_1fr] lg:grid-cols-2 lg:grid-rows-1">
        <aside className="relative isolate h-44 overflow-hidden bg-neutral-950 text-white sm:h-56 lg:m-3 lg:h-auto lg:rounded-[2rem]">
          <Photo
            photo={photo}
            sizes="(min-width: 1024px) 50vw, 100vw"
            priority
            decorative
            className="animate-drift absolute inset-0 -z-20"
          />
          <div
            aria-hidden="true"
            className="absolute inset-0 -z-10 bg-gradient-to-b from-neutral-950/70 via-neutral-950/15 to-neutral-950/80"
          />
          <div className="flex h-full flex-col justify-between px-safe pt-safe lg:p-8">
            <div className="flex h-16 items-center justify-between">
              <Link to="/" aria-label="Mentor Pilot home" className="rounded-lg">
                <Logo />
              </Link>
              <ThemeToggle />
            </div>
            <div className="hidden lg:block">
              <p className="max-w-md font-heading text-5xl leading-[1.05] font-semibold text-balance">
                {tagline}
              </p>
              <p className="mt-6 text-xs text-white/70">Photo by {photo.by} on Unsplash</p>
            </div>
          </div>
        </aside>

        <main
          id="main"
          className="relative -mt-6 flex flex-col rounded-t-[2rem] bg-background px-safe pt-8 pb-10 sm:items-center sm:px-8 lg:mt-0 lg:justify-center lg:rounded-none"
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="w-full sm:max-w-md"
          >
            <SpotlightCard className="sm:rounded-3xl sm:border sm:bg-card sm:p-8 sm:shadow-soft">
              <h1 className="text-3xl font-semibold">{title}</h1>
              {subtitle && <p className="mt-2 text-muted-foreground">{subtitle}</p>}
              <div className="mt-8">{children}</div>
            </SpotlightCard>
            {footer && <div className="mt-6 text-sm text-muted-foreground sm:text-center">{footer}</div>}
          </motion.div>
        </main>
      </div>
    </MotionConfig>
  )
}

/** Inline text links inside the sign-in pages. */
export const linkClass = 'font-medium text-primary underline-offset-4 hover:underline'
