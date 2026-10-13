import { cn } from '@/lib/utils'

/** The mark: an "M" drawn as a wired path, with the spark where it connects. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true" className={cn('size-8', className)}>
      <rect width="32" height="32" rx="9" className="fill-primary" />
      <path
        d="M9 22V11.5l7 7 7-7V22"
        className="stroke-primary-foreground"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="18.5" r="2.6" className="fill-spark" />
    </svg>
  )
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LogoMark />
      <span className="font-heading text-lg font-semibold tracking-tight">Mentor Pilot</span>
    </span>
  )
}
