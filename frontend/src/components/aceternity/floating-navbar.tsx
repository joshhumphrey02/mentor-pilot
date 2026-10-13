import { motion, useMotionValueEvent, useScroll } from 'motion/react'
import { type ReactNode, useState } from 'react'

import { cn } from '@/lib/utils'

/**
 * Adapted from Aceternity UI's Resizable Navbar: a bar that lies flat over the
 * hero, then pulls in to a floating, frosted pill once the page has scrolled.
 * `children` is called with whether the pill is showing, so the content can
 * switch from light-on-photo to the normal text colours.
 */
export function FloatingNavbar({ children }: { children: (floating: boolean) => ReactNode }) {
  const { scrollY } = useScroll()
  const [floating, setFloating] = useState(false)

  useMotionValueEvent(scrollY, 'change', (latest) => setFloating(latest > 80))

  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-40 pt-safe">
      <motion.div
        animate={{ y: floating ? 10 : 0, maxWidth: floating ? 720 : 1152 }}
        transition={{ type: 'spring', stiffness: 220, damping: 32 }}
        className={cn(
          'pointer-events-auto mx-auto flex h-16 items-center justify-between gap-2 px-safe transition-[background-color,border-color,box-shadow,border-radius,width] duration-300',
          floating
            ? 'w-[calc(100%-1.5rem)] rounded-full border bg-background/80 text-foreground shadow-soft backdrop-blur-md'
            : 'w-full border border-transparent text-white',
        )}
      >
        {children(floating)}
      </motion.div>
    </header>
  )
}
