import { lazy, Suspense } from 'react'

import { Skeleton } from '@/components/ui/skeleton'
import type { Schemas } from '@/lib/api/client'

const ChartRenderer = lazy(() => import('./chart-renderer'))

export function ChartBlock({ block }: { block: Schemas['ChartBlock'] }) {
  return (
    <figure className="rounded-2xl border bg-card p-4 shadow-soft">
      <figcaption className="mb-2 font-heading text-lg leading-snug font-semibold">
        {block.title}
      </figcaption>
      <Suspense fallback={<Skeleton className="h-[280px] w-full rounded-xl" />}>
        <ChartRenderer block={block} />
      </Suspense>

      {/* The same numbers as a table: for screen readers, and for anyone who
          wants to copy the values into their logbook. */}
      <details className="mt-2 text-sm">
        <summary className="min-h-11 cursor-pointer content-center font-medium text-primary">
          Show the data
        </summary>
        <div className="overflow-x-auto">
          <table className="mt-1 w-full border-collapse text-left">
            <thead>
              <tr className="border-b">
                <th scope="col" className="py-1.5 pr-4 font-medium">
                  Series
                </th>
                <th scope="col" className="py-1.5 pr-4 font-medium">
                  {block.x_label}
                </th>
                <th scope="col" className="py-1.5 font-medium">
                  {block.y_label}
                </th>
              </tr>
            </thead>
            <tbody>
              {block.series.flatMap((series) =>
                series.points.map((point) => (
                  <tr key={`${series.name}-${point.x}`} className="border-b last:border-0">
                    <td className="py-1.5 pr-4 text-muted-foreground">{series.name}</td>
                    <td className="py-1.5 pr-4">{point.x}</td>
                    <td className="py-1.5">{point.y}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}
