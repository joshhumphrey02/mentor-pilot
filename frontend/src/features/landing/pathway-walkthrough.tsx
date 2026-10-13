import { HandshakeIcon } from 'lucide-react'
import { useEffect, useState } from 'react'

import { PATHWAY_STAGES } from '@/features/pathway/stages'
import { useMediaQuery } from '@/hooks/use-media-query'
import { cn } from '@/lib/utils'

const HANDOFF_INDEX = 5
const STEP_MS = 2600

/**
 * The nine stages as a walkthrough that advances by itself. It stops for good
 * as soon as the visitor picks a stage, and never auto-plays for people who
 * have asked their device for less motion.
 */
export function PathwayWalkthrough() {
  const [active, setActive] = useState(0)
  const [playing, setPlaying] = useState(true)
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

  useEffect(() => {
    if (!playing || reducedMotion) return
    const timer = setInterval(
      () => setActive((index) => (index + 1) % PATHWAY_STAGES.length),
      STEP_MS,
    )
    return () => clearInterval(timer)
  }, [playing, reducedMotion])

  const stage = PATHWAY_STAGES[active] ?? PATHWAY_STAGES[0]

  return (
    <div>
      <ol className="grid grid-cols-9 gap-1.5">
        {PATHWAY_STAGES.map((item, index) => (
          <li key={item.key}>
            <button
              type="button"
              aria-label={`Stage ${index + 1}: ${item.title}`}
              aria-current={index === active ? 'step' : undefined}
              onClick={() => {
                setActive(index)
                setPlaying(false)
              }}
              className={cn(
                'grid h-11 w-full place-items-center rounded-xl font-heading text-base font-semibold transition-colors',
                index === active
                  ? 'bg-primary text-primary-foreground'
                  : index < active
                    ? 'bg-secondary text-secondary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-secondary',
              )}
            >
              {index + 1}
            </button>
          </li>
        ))}
      </ol>

      <div aria-live="polite" className="mt-4 min-h-36 rounded-2xl border bg-card p-5 shadow-soft">
        <p className="text-sm font-semibold text-primary">Stage {active + 1} of 9</p>
        <h3 className="mt-1 text-xl font-semibold">{stage.title}</h3>
        <p className="mt-1.5 text-muted-foreground">{stage.summary}</p>
        {active === HANDOFF_INDEX && (
          <p className="mt-3 inline-flex items-center gap-2 rounded-full bg-spark px-3 py-1 text-sm font-semibold text-spark-foreground">
            <HandshakeIcon aria-hidden="true" className="size-4" />A human mentor joins here
          </p>
        )}
      </div>
    </div>
  )
}
