import { motion, useMotionTemplate, useMotionValue } from 'motion/react'
import type { MouseEvent, ReactNode } from 'react'

import { cn } from '@/lib/utils'

/**
 * Adapted from Aceternity UI's Card Spotlight: a soft glow in the brand colour
 * that follows the pointer across the card. Touch screens never show it.
 */
export function SpotlightCard({ children, className }: { children: ReactNode; className?: string }) {
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const glow = useMotionTemplate`radial-gradient(320px circle at ${x}px ${y}px, color-mix(in oklch, var(--primary) 16%, transparent), transparent 75%)`

  const track = ({ currentTarget, clientX, clientY }: MouseEvent<HTMLDivElement>) => {
    const { left, top } = currentTarget.getBoundingClientRect()
    x.set(clientX - left)
    y.set(clientY - top)
  }

  return (
    <div onMouseMove={track} className={cn('group/spotlight relative', className)}>
      <motion.div
        aria-hidden="true"
        style={{ background: glow }}
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover/spotlight:opacity-100"
      />
      <div className="relative">{children}</div>
    </div>
  )
}
