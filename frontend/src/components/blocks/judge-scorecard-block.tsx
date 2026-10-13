import { ScaleIcon } from 'lucide-react'

import type { Schemas } from '@/lib/api/client'
import { cn } from '@/lib/utils'

const MAX = 5

export function JudgeScorecardBlock({ block }: { block: Schemas['JudgeScorecardBlock'] }) {
  const total = block.scores.reduce((sum, item) => sum + item.score, 0)
  const lists = [
    ['What went well', block.strengths, 'text-success'],
    ['Practise before expo', block.improvements, 'text-warning'],
  ] as const

  return (
    <section
      aria-label="Judge practice scorecard"
      className="rounded-2xl border border-insight/30 bg-insight-soft p-4"
    >
      <h3 className="flex items-center gap-2 font-heading text-lg font-semibold">
        <ScaleIcon aria-hidden="true" className="size-5 text-insight" />
        Your scorecard
        <span className="ml-auto font-sans text-base tabular-nums">
          {total} / {block.scores.length * MAX}
        </span>
      </h3>

      <ul className="mt-3 grid gap-3">
        {block.scores.map((item) => (
          <li key={item.criterion}>
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium">{item.criterion}</span>
              <span className="flex shrink-0 gap-1" role="img" aria-label={`${item.score} out of ${MAX}`}>
                {Array.from({ length: MAX }, (_, index) => index + 1).map((dot) => (
                  <span
                    key={dot}
                    className={cn('size-2.5 rounded-full', dot <= item.score ? 'bg-insight' : 'bg-border')}
                  />
                ))}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{item.comment}</p>
          </li>
        ))}
      </ul>

      {lists.map(([heading, items, tone]) => (
        <div key={heading} className="mt-4">
          <h4 className={cn('text-sm font-semibold', tone)}>{heading}</h4>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
