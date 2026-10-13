import type { Schemas } from '@/lib/api/client'

/**
 * Where everything sits on the drawn breadboard.
 *
 * The board modelled is the common half-size one: 30 columns, rows A-E above
 * the centre gap, F-J below, and two power rails along each long edge. The
 * server uses the same model to check a circuit before it is ever shown
 * (backend/app/ai/circuits.py), so the two must agree.
 */

export interface Part {
  id: string
  type: Schemas['CircuitComponent']['type']
  pins: Record<string, string>
  props: Record<string, string>
  note: string
}

export interface Wire {
  from: string
  to: string
  color: string
  note: string
}

/** One wiring of the board: the correct one, or the "Don't" version. */
export interface Layout {
  components: Part[]
  wires: Wire[]
}

/** Fills in the optional fields of the API shape, so drawing code need not check. */
export function toLayout(source: {
  components: Schemas['CircuitComponent'][]
  wires?: Schemas['CircuitWire'][]
}): Layout {
  return {
    components: source.components.map((component) => ({
      id: component.id,
      type: component.type,
      pins: component.pins,
      props: component.props ?? {},
      note: component.note ?? '',
    })),
    wires: (source.wires ?? []).map((wire) => ({
      from: wire.from,
      to: wire.to,
      color: wire.color ?? 'blue',
      note: wire.note ?? '',
    })),
  }
}

export const PITCH = 24
export const TOP_ROWS = ['A', 'B', 'C', 'D', 'E'] as const
export const BOTTOM_ROWS = ['F', 'G', 'H', 'I', 'J'] as const
const COLUMNS = 30
const MIN_VISIBLE_COLUMNS = 12
const PAD_X = 30
const RAIL_GAP = 16
const TRENCH = 26
/** Room above the board for parts that sit beside it (battery, Arduino). */
export const OFF_BOARD_BAND = 86

export type RailName = '+top' | '-top' | '+bottom' | '-bottom'
export const RAILS: RailName[] = ['+top', '-top', '+bottom', '-bottom']

export interface Point {
  x: number
  y: number
}

export interface Board {
  firstColumn: number
  lastColumn: number
  columns: number[]
  width: number
  height: number
  /** y of the top edge of the plastic board, below any off-board band. */
  top: number
  rowY: Record<string, number>
  railY: Record<RailName, number>
  columnX: (column: number) => number
  /** Position of a hole. Rails take their x from `nearColumn` when unnumbered. */
  point: (hole: string, nearColumn?: number) => Point
}

interface ParsedHole {
  rail: RailName | null
  row: string | null
  column: number | null
}

export function parseHole(hole: string): ParsedHole {
  if (hole.startsWith('+') || hole.startsWith('-')) {
    const [rail, column] = hole.split(':')
    return { rail: rail as RailName, row: null, column: column ? Number(column) : null }
  }
  return { rail: null, row: hole.charAt(0), column: Number(hole.slice(1)) }
}

/** Which metal strip a hole belongs to. Holes on one strip are connected. */
export function stripOf(hole: string): string {
  const parsed = parseHole(hole)
  if (parsed.rail) return parsed.rail
  const half = (TOP_ROWS as readonly string[]).includes(parsed.row ?? '') ? 'top' : 'bottom'
  return `${half}:${parsed.column}`
}

export function allHoles(layout: Layout): string[] {
  return [
    ...layout.components.flatMap((component) => Object.values(component.pins)),
    ...layout.wires.flatMap((wire) => [wire.from, wire.to]),
  ]
}

/**
 * Sizes the board to the columns the circuit actually uses, plus a margin.
 *
 * Drawing all 30 columns would make each hole about 10px apart on a phone.
 * Cropping to the busy part keeps holes large enough to read and to tap.
 * Both layouts of a block (Do and Don't) share one board so that switching
 * between them does not make the picture jump.
 */
export function createBoard(layouts: Layout[], hasOffBoard: boolean): Board {
  const used = layouts
    .flatMap(allHoles)
    .map((hole) => parseHole(hole).column)
    .filter((column): column is number => column !== null)
  let first = Math.max(1, (used.length ? Math.min(...used) : 1) - 2)
  let last = Math.min(COLUMNS, (used.length ? Math.max(...used) : MIN_VISIBLE_COLUMNS) + 2)
  while (last - first + 1 < MIN_VISIBLE_COLUMNS) {
    if (last < COLUMNS) last += 1
    if (last - first + 1 < MIN_VISIBLE_COLUMNS && first > 1) first -= 1
  }
  const columns = Array.from({ length: last - first + 1 }, (_, index) => first + index)

  const top = hasOffBoard ? OFF_BOARD_BAND : 8
  const railY = {} as Record<RailName, number>
  const rowY: Record<string, number> = {}
  let y = top + 22
  railY['+top'] = y
  railY['-top'] = y += PITCH
  y += RAIL_GAP
  for (const row of TOP_ROWS) rowY[row] = y += PITCH
  y += TRENCH
  for (const row of BOTTOM_ROWS) rowY[row] = y += PITCH
  y += RAIL_GAP
  railY['+bottom'] = y += PITCH
  railY['-bottom'] = y += PITCH

  const columnX = (column: number) => PAD_X + (column - first) * PITCH
  return {
    firstColumn: first,
    lastColumn: last,
    columns,
    width: PAD_X * 2 + (columns.length - 1) * PITCH,
    height: y + 26,
    top,
    rowY,
    railY,
    columnX,
    point: (hole, nearColumn) => {
      const parsed = parseHole(hole)
      const column = Math.min(last, Math.max(first, parsed.column ?? nearColumn ?? first + 1))
      return {
        x: columnX(column),
        y: parsed.rail ? railY[parsed.rail] : (rowY[parsed.row ?? 'A'] ?? 0),
      }
    },
  }
}

/** A hole name as a person would say it. */
export function describeHole(hole: string): string {
  const parsed = parseHole(hole)
  if (!parsed.rail) return hole
  const sign = parsed.rail.startsWith('+') ? 'positive' : 'negative'
  const side = parsed.rail.endsWith('top') ? 'top' : 'bottom'
  return `the ${sign} rail (${side})`
}

/** The strips that have something plugged into them: the ones carrying current. */
export function liveStrips(layout: Layout): Set<string> {
  return new Set(allHoles(layout).map(stripOf))
}
