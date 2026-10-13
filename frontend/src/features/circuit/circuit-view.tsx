import { ChevronLeftIcon, ChevronRightIcon, EyeIcon, ListOrderedIcon, XIcon } from 'lucide-react'
import { type KeyboardEvent, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import type { Schemas } from '@/lib/api/client'
import { cn } from '@/lib/utils'

import {
  BOTTOM_ROWS,
  createBoard,
  liveStrips,
  OFF_BOARD_BAND,
  parseHole,
  type Part,
  PITCH,
  type Point,
  RAILS,
  toLayout,
  TOP_ROWS,
} from './geometry'
import { drawOffBoardPart, drawPart, LIBRARY, WIRE_COLORS } from './library'
import { PartDetails } from './part-details'
import { buildSteps, componentName } from './steps'

type Mode = 'do' | 'dont'

interface CircuitViewProps {
  block: Schemas['CircuitBlock']
  /** Fetch real photos in the part details. Off for the public landing-page demo. */
  photos?: boolean
}

const LEAD_COLORS: Record<string, string> = {
  positive: '#dc2626',
  vcc: '#dc2626',
  '5V': '#dc2626',
  '3V3': '#ea580c',
  negative: '#1f2937',
  gnd: '#1f2937',
  GND: '#1f2937',
}

/** A wire that bows a little to one side, like a real jumper lying on the board. */
function wirePath(from: Point, to: Point): string {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.hypot(dx, dy) || 1
  const bow = Math.min(22, 8 + length * 0.14)
  // Perpendicular to the wire, flipped if needed so it never bows downwards
  // over the parts below it.
  let nx = dy / length
  let ny = -dx / length
  if (ny > 0) {
    nx = -nx
    ny = -ny
  }
  const mid = { x: (from.x + to.x) / 2 + nx * bow, y: (from.y + to.y) / 2 + ny * bow }
  return `M${from.x},${from.y} Q${mid.x},${mid.y} ${to.x},${to.y}`
}

/**
 * The interactive breadboard: our signature block.
 *
 * It shows three things a static picture cannot. "Reveal inside" fades the
 * plastic to show the metal strips, which is why holes in a column are
 * connected. "Do / Don't" sets the correct wiring beside a common mistake.
 * "Step through" places one part at a time, the way a teacher builds it live.
 */
export default function CircuitView({ block, photos = true }: CircuitViewProps) {
  const [mode, setMode] = useState<Mode>('do')
  const [reveal, setReveal] = useState(false)
  const [step, setStep] = useState<number | null>(null)
  const [selected, setSelected] = useState<Part | null>(null)

  const correct = useMemo(() => toLayout(block), [block])
  const mistake = useMemo(() => (block.mistake ? toLayout(block.mistake) : null), [block.mistake])
  const layout = mode === 'dont' && mistake ? mistake : correct

  const hasOffBoard = [correct, mistake].some((candidate) =>
    candidate?.components.some((part) => LIBRARY[part.type].offBoard),
  )
  const board = useMemo(
    () => createBoard(mistake ? [correct, mistake] : [correct], hasOffBoard),
    [correct, mistake, hasOffBoard],
  )
  const steps = useMemo(() => buildSteps(layout), [layout])
  const live = useMemo(() => liveStrips(layout), [layout])

  const placed = (key: string) => step === null || steps.findIndex((s) => s.key === key) <= step
  const isCurrent = (key: string) => step !== null && steps[step]?.key === key
  const powered = mode === 'do' && (step === null || step === steps.length - 1)
  const highlights = mode === 'dont' ? (block.mistake?.highlight ?? []) : (block.highlight ?? [])
  const annotations = mode === 'do' && step === null ? (block.annotations ?? []) : []
  const currentStep = step === null ? null : steps[step]

  const switchMode = (next: Mode) => {
    setMode(next)
    setStep(null)
  }

  const offBoard = layout.components.filter((part) => LIBRARY[part.type].offBoard)
  const offBoardAt = (index: number): Point => ({
    x: (board.width * (index + 1)) / (offBoard.length + 1),
    y: OFF_BOARD_BAND / 2 - 6,
  })
  const nearestColumn = (x: number) =>
    board.firstColumn + Math.round((x - board.columnX(board.firstColumn)) / PITCH)

  const openOnKey = (part: Part) => (event: KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      setSelected(part)
    }
  }

  const boardLeft = 6
  const boardWidth = board.width - 12
  const stripX = (column: number) => board.columnX(column) - 7
  const strip = (name: string) => (live.has(name) ? 'strip strip-live' : 'strip')

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {mistake && (
          <div
            role="radiogroup"
            aria-label="Correct wiring or common mistake"
            className="inline-flex rounded-xl border bg-muted p-1"
          >
            {(
              [
                ['do', 'Do'],
                ['dont', "Don't"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mode === value}
                onClick={() => switchMode(value)}
                className={cn(
                  'min-h-9 min-w-16 rounded-lg px-3 text-sm font-semibold transition-colors',
                  mode === value &&
                    (value === 'do' ? 'bg-success text-background' : 'bg-danger text-background'),
                )}
              >
                {label}
              </button>
            ))}
          </div>
        )}
        <Button
          variant={reveal ? 'default' : 'outline'}
          size="touch"
          aria-pressed={reveal}
          onClick={() => setReveal((value) => !value)}
        >
          <EyeIcon data-icon="inline-start" />
          Reveal inside
        </Button>
        {step === null && (
          <Button variant="outline" size="touch" onClick={() => setStep(0)}>
            <ListOrderedIcon data-icon="inline-start" />
            Step through
          </Button>
        )}
      </div>

      <div className="overflow-x-auto rounded-2xl border bg-[#faf7f0] p-1 dark:bg-[#2a2823]">
        <svg
          viewBox={`0 0 ${board.width} ${board.height}`}
          role="group"
          aria-label={`${block.title}: breadboard, ${mode === 'dont' ? 'showing a common mistake' : 'wired correctly'}`}
          // Scales to the space available. Wide circuits scroll sideways
          // rather than shrinking until the holes are too small to tap.
          style={{ minWidth: Math.min(board.width, 280) }}
          className="mx-auto block h-auto w-full max-w-2xl select-none"
        >
          {/* The plastic body. */}
          <rect
            x={boardLeft}
            y={board.top}
            width={boardWidth}
            height={board.height - board.top - 6}
            rx="10"
            fill="#f4efe4"
            stroke="#d6cfbf"
          />
          <rect
            x={boardLeft}
            y={(board.rowY.E ?? 0) + PITCH / 2 + 2}
            width={boardWidth}
            height={(board.rowY.F ?? 0) - (board.rowY.E ?? 0) - PITCH - 4}
            fill="#e2d9c6"
          />

          {/* Rail guide lines, as printed on a real board: red for +, blue for −. */}
          {RAILS.map((rail) => (
            <line
              key={rail}
              x1={board.columnX(board.firstColumn) - 8}
              x2={board.columnX(board.lastColumn) + 8}
              y1={board.railY[rail] + (rail.startsWith('+') ? -9 : 9)}
              y2={board.railY[rail] + (rail.startsWith('+') ? -9 : 9)}
              stroke={rail.startsWith('+') ? '#dc2626' : '#2563eb'}
              strokeWidth="1.5"
              opacity="0.7"
            />
          ))}

          {/* The metal underneath. Hidden until "Reveal inside". Strips with
              something plugged in are lit, to show where current can flow. */}
          <g aria-hidden="true" className={cn('strips', reveal && 'is-revealed')}>
            {RAILS.map((rail) => (
              <rect
                key={rail}
                x={stripX(board.firstColumn)}
                y={board.railY[rail] - 6}
                width={(board.columns.length - 1) * PITCH + 14}
                height="12"
                rx="5"
                className={strip(rail)}
              />
            ))}
            {board.columns.flatMap((column) =>
              (
                [
                  ['top', TOP_ROWS],
                  ['bottom', BOTTOM_ROWS],
                ] as const
              ).map(([half, rows]) => (
                <rect
                  key={`${half}:${column}`}
                  x={stripX(column)}
                  y={(board.rowY[rows[0]] ?? 0) - 8}
                  width="14"
                  height={(rows.length - 1) * PITCH + 16}
                  rx="6"
                  className={strip(`${half}:${column}`)}
                />
              )),
            )}
          </g>

          {/* Holes and labels. */}
          <g aria-hidden="true">
            {board.columns.map((column) => (
              <g key={column}>
                {[...TOP_ROWS, ...BOTTOM_ROWS].map((row) => (
                  <rect
                    key={row}
                    x={board.columnX(column) - 2.5}
                    y={(board.rowY[row] ?? 0) - 2.5}
                    width="5"
                    height="5"
                    rx="1"
                    fill="#4a4338"
                  />
                ))}
                {RAILS.map((rail) => (
                  <rect
                    key={rail}
                    x={board.columnX(column) - 2.5}
                    y={board.railY[rail] - 2.5}
                    width="5"
                    height="5"
                    rx="1"
                    fill="#4a4338"
                  />
                ))}
                {(column % 5 === 0 || column === 1) && (
                  <text
                    x={board.columnX(column)}
                    y={(board.rowY.E ?? 0) + PITCH / 2 + 17}
                    fontSize="9"
                    textAnchor="middle"
                    fill="#8a8170"
                  >
                    {column}
                  </text>
                )}
              </g>
            ))}
            {[...TOP_ROWS, ...BOTTOM_ROWS].map((row) => (
              <text
                key={row}
                x={boardLeft + 8}
                y={(board.rowY[row] ?? 0) + 3}
                fontSize="9"
                textAnchor="middle"
                fill="#8a8170"
              >
                {row}
              </text>
            ))}
            {RAILS.map((rail) => (
              <text
                key={rail}
                x={boardLeft + 8}
                y={board.railY[rail] + 4}
                fontSize="12"
                fontWeight="700"
                textAnchor="middle"
                fill={rail.startsWith('+') ? '#dc2626' : '#2563eb'}
              >
                {rail.startsWith('+') ? '+' : '−'}
              </text>
            ))}
          </g>

          {/* Rings around the holes being pointed out. */}
          <g aria-hidden="true">
            {highlights.map((hole) => {
              const at = board.point(hole)
              return (
                <circle
                  key={hole}
                  cx={at.x}
                  cy={at.y}
                  r="10"
                  fill="none"
                  strokeWidth="2.5"
                  className={cn('hole-ring', mode === 'dont' ? 'stroke-[#dc2626]' : 'stroke-[#3b43d6]')}
                />
              )
            })}
          </g>

          {/* Parts and wires fade a little during the reveal, so the strips show through. */}
          <g className={cn('transition-opacity duration-500', reveal && 'opacity-45')}>
            {layout.wires.map((wire, index) => {
              const key = `wire:${index}`
              const from = board.point(wire.from, parseHole(wire.to).column ?? undefined)
              const to = board.point(wire.to, parseHole(wire.from).column ?? undefined)
              return (
                <g
                  // Wires have no id; their position in the list identifies them.
                  // oxlint-disable-next-line react/no-array-index-key
                  key={key}
                  aria-hidden="true"
                  className={cn('part', !placed(key) && 'is-hidden', isCurrent(key) && 'is-current')}
                >
                  <path
                    d={wirePath(from, to)}
                    fill="none"
                    stroke={WIRE_COLORS[wire.color] ?? WIRE_COLORS.blue}
                    strokeWidth="4"
                    strokeLinecap="round"
                  />
                  <circle cx={from.x} cy={from.y} r="3.5" fill="#6b7280" />
                  <circle cx={to.x} cy={to.y} r="3.5" fill="#6b7280" />
                </g>
              )
            })}

            {layout.components.map((part) => {
              const key = `component:${part.id}`
              const info = LIBRARY[part.type]
              const label = `${componentName(part)}. ${Object.entries(part.pins)
                .map(([pin, hole]) => `${pin} in ${hole}`)
                .join(', ')}. Tap for details.`
              const shared = {
                role: 'button' as const,
                tabIndex: placed(key) ? 0 : -1,
                'aria-label': label,
                'aria-hidden': placed(key) ? undefined : true,
                onClick: () => setSelected(part),
                onKeyDown: openOnKey(part),
                className: cn(
                  'part cursor-pointer outline-none',
                  !placed(key) && 'is-hidden',
                  isCurrent(key) && 'is-current',
                ),
              }

              if (info.offBoard) {
                const at = offBoardAt(offBoard.indexOf(part))
                const pins = Object.entries(part.pins)
                return (
                  <g key={key} {...shared}>
                    {pins.map(([pin, hole], index) => {
                      const spread = pins.length === 2 ? 48 : 16
                      const start = { x: at.x + (index - (pins.length - 1) / 2) * spread, y: at.y + 20 }
                      const end = board.point(hole, nearestColumn(start.x))
                      return (
                        <path
                          key={pin}
                          d={`M${start.x},${start.y} C${start.x},${start.y + 26} ${end.x},${end.y - 30} ${end.x},${end.y}`}
                          fill="none"
                          stroke={LEAD_COLORS[pin] ?? '#ca8a04'}
                          strokeWidth="3.5"
                          strokeLinecap="round"
                        />
                      )
                    })}
                    {drawOffBoardPart(part.type, at, part.props)}
                    <rect x={at.x - 50} y={at.y - 26} width="100" height="52" fill="transparent" className="focus-ring" />
                  </g>
                )
              }

              const firstColumn = Object.values(part.pins)
                .map((hole) => parseHole(hole).column)
                .find((column) => column !== null)
              const pins: Record<string, Point> = Object.fromEntries(
                Object.entries(part.pins).map(([pin, hole]) => [
                  pin,
                  board.point(hole, firstColumn ?? undefined),
                ]),
              )
              const xs = Object.values(pins).map((point) => point.x)
              const ys = Object.values(pins).map((point) => point.y)
              return (
                <g key={key} {...shared}>
                  {drawPart(part.type, { pins, props: part.props, powered })}
                  {/* A generous invisible target: parts are small, fingers are not. */}
                  <rect
                    x={Math.min(...xs) - 16}
                    y={Math.min(...ys) - 40}
                    width={Math.max(...xs) - Math.min(...xs) + 32}
                    height={Math.max(...ys) - Math.min(...ys) + 56}
                    rx="8"
                    fill="transparent"
                    className="focus-ring"
                  />
                </g>
              )
            })}
          </g>

          {/* Numbered markers; their text is listed under the board. */}
          <g aria-hidden="true">
            {annotations.map((annotation, index) => {
              const at = board.point(annotation.at)
              return (
                <g key={annotation.at}>
                  {/* Below-left of the hole, clear of a part sitting to its right. */}
                  <circle cx={at.x - 13} cy={at.y + 14} r="8" fill="#3b43d6" />
                  <text
                    x={at.x - 13}
                    y={at.y + 17.5}
                    fontSize="10"
                    fontWeight="700"
                    textAnchor="middle"
                    fill="white"
                  >
                    {index + 1}
                  </text>
                </g>
              )
            })}
          </g>
        </svg>
      </div>

      {mode === 'dont' && block.mistake && (
        <div role="status" className="rounded-2xl border border-danger/40 bg-danger-soft p-4">
          <p className="font-semibold text-danger">Don't: {block.mistake.title}</p>
          <p className="mt-1">{block.mistake.explanation}</p>
        </div>
      )}

      {reveal && (
        <p role="status" className="rounded-2xl bg-muted p-3 text-sm">
          Under the plastic, each column of five holes sits on one metal strip, so anything in the
          same column is connected. The long rails run the whole length. The lit strips are the
          ones carrying current in this circuit.
        </p>
      )}

      {currentStep && step !== null && (
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-sm font-medium text-muted-foreground">
            Step {step + 1} of {steps.length}
          </p>
          <p aria-live="polite" className="mt-1">
            {currentStep.text}
            {currentStep.note && (
              <span className="mt-1 block text-sm text-muted-foreground">{currentStep.note}</span>
            )}
          </p>
          <div className="mt-3 flex items-center gap-2">
            <Button
              variant="outline"
              size="touch"
              disabled={step === 0}
              onClick={() => setStep(step - 1)}
            >
              <ChevronLeftIcon data-icon="inline-start" />
              Back
            </Button>
            <Button
              size="touch"
              disabled={step === steps.length - 1}
              onClick={() => setStep(step + 1)}
            >
              Next
              <ChevronRightIcon data-icon="inline-end" />
            </Button>
            <Button
              variant="ghost"
              size="icon-touch"
              className="ml-auto"
              aria-label="Stop stepping and show the whole circuit"
              onClick={() => setStep(null)}
            >
              <XIcon />
            </Button>
          </div>
        </div>
      )}

      {annotations.length > 0 && (
        <ol className="grid gap-1 text-sm">
          {annotations.map((annotation, index) => (
            <li key={annotation.at} className="flex gap-2">
              <span
                aria-hidden="true"
                className="grid size-5 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground"
              >
                {index + 1}
              </span>
              <span>
                <span className="sr-only">At {annotation.at}: </span>
                {annotation.text}
              </span>
            </li>
          ))}
        </ol>
      )}

      {/* The whole build in words: for screen readers, and for copying into a logbook. */}
      <details className="text-sm">
        <summary className="min-h-11 cursor-pointer content-center font-medium text-primary">
          Read the wiring as text
        </summary>
        <ol className="mt-1 list-decimal space-y-1 pl-5">
          {steps.map((item) => (
            <li key={item.key}>{item.text}</li>
          ))}
        </ol>
      </details>

      <PartDetails part={selected} onClose={() => setSelected(null)} photos={photos} />
    </div>
  )
}
