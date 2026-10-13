import { RecycleIcon } from 'lucide-react'

import type { Schemas } from '@/lib/api/client'

const rand = new Intl.NumberFormat('en-ZA', { style: 'currency', currency: 'ZAR' })

export function BomTableBlock({ block }: { block: Schemas['BomTableBlock'] }) {
  return (
    <section aria-label={block.title} className="rounded-2xl border bg-card shadow-soft">
      <h3 className="px-4 pt-4 font-heading text-lg font-semibold">{block.title}</h3>

      <ul className="mt-2 divide-y">
        {block.items.map((item) => (
          <li key={item.name} className="px-4 py-3">
            <div className="flex items-baseline justify-between gap-3">
              <p className="min-w-0 font-medium">
                {item.name}
                <span className="font-normal text-muted-foreground"> × {item.quantity}</span>
              </p>
              <p className="shrink-0 tabular-nums">
                {item.unit_price_zar === 0
                  ? 'Free'
                  : rand.format(item.quantity * item.unit_price_zar)}
              </p>
            </div>
            {(item.where_to_get || (item.unit_price_zar > 0 && item.quantity > 1)) && (
              <p className="text-sm text-muted-foreground">
                {[
                  item.unit_price_zar > 0 && item.quantity > 1
                    ? `${rand.format(item.unit_price_zar)} each`
                    : '',
                  item.where_to_get,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            )}
            {item.substitute && (
              <p className="mt-1.5 flex items-start gap-1.5 text-sm text-success">
                <RecycleIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                <span>
                  <span className="font-medium">Save money:</span>{' '}
                  <span className="text-foreground">{item.substitute}</span>
                </span>
              </p>
            )}
          </li>
        ))}
      </ul>

      <p className="flex items-baseline justify-between gap-3 rounded-b-2xl border-t bg-muted px-4 py-3 font-semibold">
        Estimated total
        <span className="text-lg tabular-nums">{rand.format(block.total_zar)}</span>
      </p>
      <p className="px-4 py-2 text-xs text-muted-foreground">
        Prices are estimates. Check a local shop before you buy.
      </p>
    </section>
  )
}
