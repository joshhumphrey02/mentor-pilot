import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { Schemas } from '@/lib/api/client'

type Chart = Schemas['ChartBlock']

// The chart tokens from index.css, which are tuned for both themes.
const COLORS = [1, 2, 3, 4, 5].map((n) => `var(--chart-${n})`)
const color = (index: number) => COLORS[index % COLORS.length]

const axis = { stroke: 'var(--muted-foreground)', fontSize: 12 }
const tooltip = {
  contentStyle: {
    background: 'var(--popover)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    color: 'var(--popover-foreground)',
  },
}

/**
 * Line and bar charts need one row per x value with a column per series.
 * Series do not have to share the same x values, so rows are merged by x.
 */
function toRows(series: Chart['series']) {
  const rows = new Map<string | number, Record<string, string | number>>()
  for (const item of series) {
    for (const point of item.points) {
      const row = rows.get(point.x) ?? { x: point.x }
      row[item.name] = point.y
      rows.set(point.x, row)
    }
  }
  const merged = [...rows.values()]
  const numeric = merged.every((row) => typeof row.x === 'number')
  return numeric ? merged.sort((a, b) => Number(a.x) - Number(b.x)) : merged
}

/** Recharts is a separate chunk, loaded only when a message contains a chart. */
export default function ChartRenderer({ block }: { block: Chart }) {
  const rows = toRows(block.series)
  const numericX = rows.every((row) => typeof row.x === 'number')
  const margin = { top: 8, right: 12, bottom: 24, left: 4 }
  const xLabel = { value: block.x_label, position: 'insideBottom' as const, offset: -14, ...axis }
  const yLabel = {
    value: block.y_label,
    angle: -90,
    position: 'insideLeft' as const,
    style: { textAnchor: 'middle' as const },
    ...axis,
  }
  const legend = block.series.length > 1 ? <Legend verticalAlign="top" height={28} /> : null

  if (block.chart_type === 'scatter') {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={margin}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="x" type="number" name={block.x_label} label={xLabel} {...axis} />
          <YAxis dataKey="y" type="number" name={block.y_label} label={yLabel} {...axis} />
          <Tooltip {...tooltip} cursor={{ strokeDasharray: '3 3' }} />
          {legend}
          {block.series.map((item, index) => (
            <Scatter key={item.name} name={item.name} data={item.points} fill={color(index)} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  if (block.chart_type === 'bar') {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} margin={margin}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="x" label={xLabel} {...axis} />
          <YAxis label={yLabel} {...axis} />
          <Tooltip {...tooltip} cursor={{ fill: 'var(--muted)' }} />
          {legend}
          {block.series.map((item, index) => (
            <Bar key={item.name} dataKey={item.name} fill={color(index)} radius={[6, 6, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={rows} margin={margin}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
        <XAxis
          dataKey="x"
          type={numericX ? 'number' : 'category'}
          domain={numericX ? ['dataMin', 'dataMax'] : undefined}
          label={xLabel}
          {...axis}
        />
        <YAxis label={yLabel} {...axis} />
        <Tooltip {...tooltip} />
        {legend}
        {block.series.map((item, index) => (
          <Line
            key={item.name}
            type="monotone"
            dataKey={item.name}
            stroke={color(index)}
            strokeWidth={2.5}
            dot={{ r: 4 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
