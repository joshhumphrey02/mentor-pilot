import { BanknoteIcon, ClockIcon, ShieldAlertIcon, ShieldCheckIcon, TrophyIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useWorkspace } from '@/features/chat/workspace-context'
import type { Schemas } from '@/lib/api/client'
import { cn } from '@/lib/utils'

type Idea = Schemas['IdeaCard']

const rand = new Intl.NumberFormat('en-ZA', {
  style: 'currency',
  currency: 'ZAR',
  maximumFractionDigits: 0,
})

const SAFETY: Record<Idea['safety_level'], { label: string; className: string }> = {
  low: { label: 'Low risk', className: 'bg-success-soft text-success' },
  medium: { label: 'Take care', className: 'bg-warning-soft text-warning' },
  high: { label: 'Needs an adult', className: 'bg-danger-soft text-danger' },
}

function Difficulty({ level }: { level: number }) {
  return (
    <span className="inline-flex items-center gap-1.5" title={`Difficulty ${level} out of 5`}>
      <span className="sr-only">Difficulty {level} out of 5</span>
      <span aria-hidden="true" className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((dot) => (
          <span
            key={dot}
            className={cn('size-2 rounded-full', dot <= level ? 'bg-primary' : 'bg-border')}
          />
        ))}
      </span>
    </span>
  )
}

function IdeaCardView({ idea }: { idea: Idea }) {
  const workspace = useWorkspace()
  const safety = SAFETY[idea.safety_level]
  const SafetyIcon = idea.safety_level === 'low' ? ShieldCheckIcon : ShieldAlertIcon
  const cost =
    idea.cost_max_zar === 0
      ? 'Free'
      : idea.cost_min_zar === idea.cost_max_zar
        ? rand.format(idea.cost_max_zar)
        : `${rand.format(idea.cost_min_zar)} – ${rand.format(idea.cost_max_zar)}`
  const say = (text: string) => workspace?.send(text)

  return (
    <article className="flex h-full flex-col rounded-2xl border bg-card p-4 shadow-soft">
      <p className="text-xs font-semibold tracking-wide text-primary uppercase">{idea.field}</p>
      <h3 className="mt-1 font-heading text-lg leading-snug font-semibold">{idea.title}</h3>
      <p className="mt-1.5 text-sm text-muted-foreground">{idea.problem}</p>

      <dl className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm">
        <div className="flex items-center gap-1.5">
          <dt className="sr-only">Difficulty</dt>
          <dd>
            <Difficulty level={idea.difficulty} />
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <dt>
            <BanknoteIcon aria-hidden="true" className="size-4 text-muted-foreground" />
            <span className="sr-only">Cost</span>
          </dt>
          <dd>{cost}</dd>
        </div>
        <div className="flex items-center gap-1.5">
          <dt>
            <ClockIcon aria-hidden="true" className="size-4 text-muted-foreground" />
            <span className="sr-only">Time needed</span>
          </dt>
          <dd>{idea.time_needed}</dd>
        </div>
      </dl>

      {idea.materials.length > 0 && (
        <ul aria-label="Materials" className="mt-3 flex flex-wrap gap-1.5">
          {idea.materials.map((material) => (
            <li key={material} className="rounded-full bg-muted px-2.5 py-0.5 text-xs">
              {material}
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 flex gap-2 text-sm">
        <TrophyIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-insight" />
        <span>
          <span className="sr-only">Why judges like it: </span>
          {idea.why_judges_like_it}
        </span>
      </p>

      <p
        className={cn(
          'mt-3 flex items-start gap-2 rounded-xl px-2.5 py-1.5 text-sm',
          safety.className,
        )}
      >
        <SafetyIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>
          <span className="font-semibold">{safety.label}</span>
          {idea.safety_note && <span className="text-foreground"> · {idea.safety_note}</span>}
        </span>
      </p>

      {workspace && (
        // mt-auto pins the actions to the bottom so cards of different
        // lengths line up their buttons.
        <div className="mt-auto grid grid-cols-2 gap-2 pt-4">
          <Button
            variant="outline"
            size="touch"
            disabled={workspace.busy}
            onClick={() => say(`Tell me more about “${idea.title}”.`)}
          >
            Explore
          </Button>
          <Button
            variant="outline"
            size="touch"
            disabled={workspace.busy}
            onClick={() => say(`Compare “${idea.title}” with the other ideas.`)}
          >
            Compare
          </Button>
          <Button
            size="touch"
            className="col-span-2"
            disabled={workspace.busy}
            onClick={() => say(`I choose “${idea.title}”.`)}
          >
            Choose this
          </Button>
        </div>
      )}
    </article>
  )
}

/** Project ideas: a swipeable row on phones, a grid on wider screens. */
export function IdeaCardsBlock({ block }: { block: Schemas['IdeaCardsBlock'] }) {
  return (
    <ul
      aria-label="Project ideas"
      // The row bleeds to the screen edges on phones so the next card peeks
      // in, which is what tells you it can be swiped.
      className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 [scrollbar-width:none] sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0"
    >
      {block.ideas.map((idea) => (
        <li key={idea.title} className="w-[85%] shrink-0 snap-center sm:w-auto">
          <IdeaCardView idea={idea} />
        </li>
      ))}
    </ul>
  )
}
