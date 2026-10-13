import { useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/api/errors'

import { type Dataset, datasetsQueryOptions, useSaveDataset } from './api'
import { toChart } from './data-chart'

const ChartRenderer = lazy(() => import('@/components/blocks/chart-renderer'))

const MAX_COLUMNS = 8
const cell =
  'h-11 w-full min-w-20 bg-transparent px-2 text-base outline-none focus-visible:bg-secondary'

function DatasetEditor({ projectId, dataset }: { projectId: string; dataset: Dataset | null }) {
  const save = useSaveDataset(projectId)
  const [title, setTitle] = useState(dataset?.title ?? 'My results')
  const [columns, setColumns] = useState(dataset?.columns ?? ['Trial', 'Measurement'])
  const [rows, setRows] = useState(dataset?.rows.length ? dataset.rows : [['1', ''], ['2', ''], ['3', '']])
  const [dirty, setDirty] = useState(dataset === null)
  const chart = toChart(title, columns, rows)

  const edit = (change: () => void) => {
    change()
    setDirty(true)
  }

  return (
    <section className="grid gap-3 rounded-2xl border bg-card p-3">
      <input
        aria-label="Table title"
        value={title}
        maxLength={160}
        onChange={(event) => edit(() => setTitle(event.target.value))}
        className="h-11 rounded-lg bg-transparent px-2 font-heading text-lg font-semibold outline-none focus-visible:bg-secondary"
      />

      <div className="overflow-x-auto rounded-xl border">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-muted">
              {columns.map((column, index) => (
                // Columns have no id of their own; position is their identity.
                // oxlint-disable-next-line react/no-array-index-key
                <th key={index} scope="col" className="border-r p-0 last:border-r-0">
                  <input
                    aria-label={`Column ${index + 1} heading`}
                    value={column}
                    maxLength={120}
                    onChange={(event) =>
                      edit(() =>
                        setColumns(columns.map((old, at) => (at === index ? event.target.value : old))),
                      )
                    }
                    className={`${cell} font-semibold`}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              // oxlint-disable-next-line react/no-array-index-key
              <tr key={rowIndex} className="border-t">
                {columns.map((column, columnIndex) => (
                  // oxlint-disable-next-line react/no-array-index-key
                  <td key={columnIndex} className="border-r p-0 last:border-r-0">
                    <input
                      aria-label={`${column || `Column ${columnIndex + 1}`}, row ${rowIndex + 1}`}
                      value={row[columnIndex] ?? ''}
                      maxLength={120}
                      inputMode={columnIndex > 0 ? 'decimal' : 'text'}
                      onChange={(event) =>
                        edit(() =>
                          setRows(
                            rows.map((old, at) =>
                              at === rowIndex
                                ? columns.map((_, c) => (c === columnIndex ? event.target.value : (old[c] ?? '')))
                                : old,
                            ),
                          ),
                        )
                      }
                      className={cell}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="touch"
          onClick={() => edit(() => setRows([...rows, columns.map((_, c) => (c === 0 ? String(rows.length + 1) : ''))]))}
        >
          <PlusIcon data-icon="inline-start" />
          Row
        </Button>
        <Button
          variant="outline"
          size="touch"
          disabled={columns.length >= MAX_COLUMNS}
          onClick={() =>
            edit(() => {
              setColumns([...columns, `Column ${columns.length + 1}`])
              setRows(rows.map((row) => [...row, '']))
            })
          }
        >
          <PlusIcon data-icon="inline-start" />
          Column
        </Button>
        {dirty && (
          <Button
            size="touch"
            className="ml-auto"
            disabled={save.isPending}
            onClick={async () => {
              try {
                await save.mutateAsync({ id: dataset?.id ?? null, data: { title, columns, rows } })
                setDirty(false)
                toast.success('Saved')
              } catch (error) {
                toast.error(errorMessage(error))
              }
            }}
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
        )}
      </div>

      {chart ? (
        <Suspense fallback={<Skeleton className="h-[280px] w-full rounded-xl" />}>
          <ChartRenderer block={chart} />
        </Suspense>
      ) : (
        <p className="text-sm text-muted-foreground">
          Type numbers into a column and a graph of them will appear here.
        </p>
      )}
    </section>
  )
}

/** Tables of the learner's own measurements, each with a live graph. */
export function DataTab({ projectId }: { projectId: string }) {
  const datasets = useQuery(datasetsQueryOptions(projectId))
  const [adding, setAdding] = useState(false)

  if (datasets.isPending) return <Skeleton className="h-40 rounded-xl" />
  const none = datasets.data?.length === 0

  return (
    <div className="grid gap-4">
      {datasets.data?.map((dataset) => (
        <DatasetEditor key={dataset.id} projectId={projectId} dataset={dataset} />
      ))}
      {(adding || none) && <DatasetEditor key={`new-${datasets.data?.length}`} projectId={projectId} dataset={null} />}
      {!adding && !none && (
        <Button variant="outline" size="touch" onClick={() => setAdding(true)} className="justify-self-start">
          <PlusIcon data-icon="inline-start" />
          Another table
        </Button>
      )}
      <p className="text-sm text-muted-foreground">
        Only record what you actually measured. Messy results are still results.
      </p>
    </div>
  )
}
