import type { Schemas } from '@/lib/api/client'

/** Reads a cell as a number, accepting a decimal comma ("3,5"), as written in South Africa. */
export function toNumber(text: string): number | null {
  const value = Number(text.trim().replace(',', '.'))
  return text.trim() !== '' && Number.isFinite(value) ? value : null
}

/**
 * Turns a table into a chart: the first column is the x axis, and every other
 * column that holds numbers becomes a series. Rows without a number are skipped.
 */
export function toChart(title: string, columns: string[], rows: string[][]): Schemas['ChartBlock'] | null {
  const [xLabel, ...rest] = columns
  if (xLabel === undefined) return null
  const numericX = rows.every((row) => !row[0]?.trim() || toNumber(row[0]) !== null)
  const series = rest
    .map((name, index) => ({
      name: name || `Column ${index + 2}`,
      points: rows.flatMap((row) => {
        const y = toNumber(row[index + 1] ?? '')
        const label = row[0]?.trim() ?? ''
        if (y === null || !label) return []
        return [{ x: numericX ? (toNumber(label) ?? label) : label, y }]
      }),
    }))
    .filter((item) => item.points.length > 0)
  if (series.length === 0) return null
  return {
    type: 'chart',
    chart_type: numericX ? 'line' : 'bar',
    title,
    x_label: xLabel,
    y_label: series.length === 1 ? (series[0]?.name ?? '') : 'Value',
    series,
  }
}
