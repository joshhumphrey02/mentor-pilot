import { FlaskConicalIcon } from 'lucide-react'

import type { Schemas } from '@/lib/api/client'

type Plan = Schemas['ExperimentPlanBlock']

const rowKeys = (count: number) => Array.from({ length: count }, (_, index) => index + 1)

export function ExperimentPlanBlock({ block }: { block: Plan }) {
  const variables = [
    ['What you change', 'Independent variable', block.independent_variable],
    ['What you measure', 'Dependent variable', block.dependent_variable],
  ] as const

  return (
    <section
      aria-label={block.title}
      className="rounded-2xl border bg-card p-4 shadow-soft"
    >
      <h3 className="flex items-center gap-2 font-heading text-lg leading-snug font-semibold">
        <FlaskConicalIcon aria-hidden="true" className="size-5 shrink-0 text-primary" />
        {block.title}
      </h3>

      <dl className="mt-3 grid gap-3">
        {variables.map(([plain, term, value]) => (
          <div key={term}>
            <dt className="text-sm font-semibold">
              {plain} <span className="font-normal text-muted-foreground">({term})</span>
            </dt>
            <dd>{value}</dd>
          </div>
        ))}
        <div>
          <dt className="text-sm font-semibold">
            What you keep the same{' '}
            <span className="font-normal text-muted-foreground">(Controlled variables)</span>
          </dt>
          <dd>
            <ul className="list-disc pl-5">
              {block.controlled_variables.map((variable) => (
                <li key={variable}>{variable}</li>
              ))}
            </ul>
          </dd>
        </div>
        <div>
          <dt className="text-sm font-semibold">Trials</dt>
          <dd>
            Repeat each test {block.trials} {block.trials === 1 ? 'time' : 'times'}.
          </dd>
        </div>
      </dl>

      <h4 className="mt-4 text-sm font-semibold">Your data table</h4>
      <div className="mt-1.5 overflow-x-auto rounded-xl border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-muted text-left">
              {block.data_table.columns.map((column) => (
                <th key={column} scope="col" className="p-2.5 font-medium whitespace-nowrap">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowKeys(block.data_table.rows).map((row) => (
              <tr key={row} className="border-t">
                {block.data_table.columns.map((column) => (
                  <td key={column} className="h-10 p-2.5">
                    <span className="sr-only">blank</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        Copy this table into your logbook and fill it in as you run each trial.
      </p>
    </section>
  )
}
