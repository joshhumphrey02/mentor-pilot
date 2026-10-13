import type { Schemas } from '@/lib/api/client'

/** A comparison: a table where there is room, one card per option on phones. */
export function ComparisonTableBlock({ block }: { block: Schemas['ComparisonTableBlock'] }) {
  return (
    <figure>
      {block.title && (
        <figcaption className="mb-2 font-heading text-lg font-semibold">{block.title}</figcaption>
      )}

      <div className="hidden overflow-x-auto rounded-2xl border sm:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-muted text-left">
              <th scope="col" className="p-3">
                <span className="sr-only">Criterion</span>
              </th>
              {block.options.map((option) => (
                <th key={option} scope="col" className="p-3 font-semibold">
                  {option}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row) => (
              <tr key={row.criterion} className="border-t align-top">
                <th scope="row" className="p-3 text-left font-medium text-muted-foreground">
                  {row.criterion}
                </th>
                {block.options.map((option, column) => (
                  <td key={option} className="p-3">
                    {row.values[column]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="grid gap-3 sm:hidden">
        {block.options.map((option, column) => (
          <li key={option} className="rounded-2xl border bg-card p-4">
            <h3 className="font-heading text-base font-semibold">{option}</h3>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              {block.rows.map((row) => (
                <div key={row.criterion} className="contents">
                  <dt className="text-muted-foreground">{row.criterion}</dt>
                  <dd>{row.values[column]}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </figure>
  )
}
