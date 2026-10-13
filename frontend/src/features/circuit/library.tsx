import type { ReactNode } from 'react'

import type { Schemas } from '@/lib/api/client'

import type { Point } from './geometry'

/**
 * The component library: how each part is described and drawn.
 *
 * To add a part, add an entry here and to COMPONENTS in
 * backend/app/ai/circuits.py (and to the ComponentType list in blocks.py).
 */

export type ComponentType = Schemas['CircuitComponent']['type']

export interface PartInfo {
  label: string
  /** What it does, in a sentence or two a Grade 8 learner can follow. */
  summary: string
  /** What each leg is for. */
  pins: Record<string, string>
  /** Sits beside the board and reaches it with leads. */
  offBoard?: boolean
}

export const LIBRARY: Record<ComponentType, PartInfo> = {
  led: {
    label: 'LED',
    summary:
      'A light-emitting diode. It lights up when current flows through it, and it only lets current flow one way, so it must be the right way round.',
    pins: {
      anode: 'The long leg. Goes towards positive (+).',
      cathode: 'The short leg, on the flat side. Goes towards negative (−).',
    },
  },
  resistor: {
    label: 'Resistor',
    summary:
      'Limits how much current flows. An LED needs one, or it draws too much current and burns out. It works either way round. The coloured bands show its value in ohms (Ω).',
    pins: { a: 'Either leg: a resistor has no direction.', b: 'The other leg.' },
  },
  button: {
    label: 'Push button',
    summary:
      'A switch that connects its two sides only while you press it. Let go and the circuit is broken again.',
    pins: { a: 'One side of the switch.', b: 'The other side.' },
  },
  buzzer: {
    label: 'Buzzer',
    summary: 'Makes a sound when current flows through it. It has a positive and a negative leg.',
    pins: {
      positive: 'The longer leg, marked +. Goes towards positive.',
      negative: 'The shorter leg. Goes towards negative.',
    },
  },
  ldr: {
    label: 'Light sensor (LDR)',
    summary:
      'A light-dependent resistor. Its resistance drops when light shines on it, so a circuit can tell bright from dark. It works either way round.',
    pins: { a: 'Either leg: an LDR has no direction.', b: 'The other leg.' },
  },
  potentiometer: {
    label: 'Potentiometer',
    summary:
      'A resistor you can adjust by turning a knob, like a volume control. The middle leg gives a voltage that changes as you turn it.',
    pins: {
      a: 'One end of the track. Usually to positive.',
      wiper: 'The middle leg. Its voltage changes as you turn the knob.',
      b: 'The other end of the track. Usually to negative.',
    },
  },
  battery: {
    label: 'Battery pack',
    summary:
      'The power source. Two AA cells give about 3 volts, which is safe to touch. Never join its two wires directly: that is a short circuit.',
    pins: {
      positive: 'The red wire (+).',
      negative: 'The black wire (−).',
    },
    offBoard: true,
  },
  arduino_uno: {
    label: 'Arduino Uno',
    summary:
      'A small programmable computer. Your code switches its pins on and off and reads sensors. It runs at 5 volts from a USB cable.',
    pins: {
      '5V': 'A steady 5 volt supply.',
      '3V3': 'A steady 3.3 volt supply.',
      GND: 'Ground: the negative side of the circuit.',
      D: 'Digital pins (D0–D13) are switched on or off by your code.',
      A: 'Analog pins (A0–A5) measure a voltage, for sensors.',
    },
    offBoard: true,
  },
  ultrasonic: {
    label: 'Ultrasonic sensor',
    summary:
      'Measures distance by sending out a sound too high to hear and timing its echo, like a bat.',
    pins: {
      vcc: 'Power in (5 volts).',
      trig: 'Trigger: tells the sensor to send a pulse.',
      echo: 'Echo: reports how long the sound took to come back.',
      gnd: 'Ground (negative).',
    },
  },
  servo: {
    label: 'Servo motor',
    summary:
      'A motor that turns to an exact angle and holds it. Used for arms, flaps and steering.',
    pins: {
      signal: 'The control wire (usually orange or yellow). Tells it which angle.',
      vcc: 'Power (the red wire).',
      gnd: 'Ground (the brown or black wire).',
    },
    offBoard: true,
  },
  dc_motor: {
    label: 'DC motor',
    summary:
      'Spins when current flows through it. Swap its two wires and it spins the other way.',
    pins: { a: 'One terminal.', b: 'The other terminal.' },
    offBoard: true,
  },
}

/** Describes a pin, including the Arduino's numbered ones. */
export function pinHelp(type: ComponentType, pin: string): string {
  const pins = LIBRARY[type].pins
  return pins[pin] ?? pins[pin.charAt(0)] ?? ''
}

const LED_COLORS: Record<string, string> = {
  red: '#ef4444',
  green: '#22c55e',
  yellow: '#facc15',
  blue: '#3b82f6',
  white: '#f8fafc',
  orange: '#fb923c',
}

export const WIRE_COLORS: Record<string, string> = {
  red: '#dc2626',
  black: '#1f2937',
  blue: '#2563eb',
  green: '#16a34a',
  yellow: '#ca8a04',
  orange: '#ea580c',
  white: '#e5e7eb',
  purple: '#9333ea',
}

// A board-coloured outline behind small labels, so they stay readable where
// they sit on top of a row of holes.
const LABEL_HALO = {
  stroke: '#f4efe4',
  strokeWidth: 3.5,
  paintOrder: 'stroke' as const,
  strokeLinejoin: 'round' as const,
}

const LEG = { stroke: '#8b8f98', strokeWidth: 2.5, strokeLinecap: 'round' as const, fill: 'none' }
const midpoint = (a: Point, b: Point): Point => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 })
const angle = (a: Point, b: Point) => (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI

interface DrawArgs {
  /** Where each of the part's legs enters the board, by pin name. */
  pins: Record<string, Point>
  props: Record<string, string>
  /** True once the whole circuit is built correctly: an LED glows. */
  powered: boolean
}

/** Draws an on-board part across the holes its legs are in. */
export function drawPart(type: ComponentType, { pins, props, powered }: DrawArgs): ReactNode {
  const points = Object.values(pins)
  const [first, second] = points
  if (!first) return null
  const last = points[points.length - 1] ?? first
  const centre = midpoint(first, last)

  switch (type) {
    case 'led': {
      // Seen from above, as it looks pushed into the board: a dome sitting
      // over its two holes, with the legs disappearing underneath.
      const anode = pins.anode ?? first
      const cathode = pins.cathode ?? second ?? first
      const dome = midpoint(anode, cathode)
      const fill = LED_COLORS[props.color ?? 'red'] ?? LED_COLORS.red
      // Nudge the "+" away from the dome, on the anode's side.
      const away = Math.hypot(anode.x - dome.x, anode.y - dome.y) || 1
      const mark = {
        x: anode.x + ((anode.x - dome.x) / away) * 13,
        y: anode.y + ((anode.y - dome.y) / away) * 13,
      }
      return (
        <>
          <path d={`M${anode.x},${anode.y} L${cathode.x},${cathode.y}`} {...LEG} />
          {powered && <circle cx={dome.x} cy={dome.y} r="22" fill={fill} className="led-glow" />}
          <circle
            cx={dome.x}
            cy={dome.y}
            r="11"
            fill={fill}
            fillOpacity={powered ? 1 : 0.5}
            stroke="rgb(0 0 0 / 0.4)"
            strokeWidth="1"
          />
          <circle cx={dome.x - 3.5} cy={dome.y - 3.5} r="3" fill="white" fillOpacity="0.6" />
          <text
            x={mark.x}
            y={mark.y + 4}
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            fill="#b91c1c"
            {...LABEL_HALO}
          >
            +
          </text>
        </>
      )
    }
    case 'resistor':
    case 'ldr': {
      const a = pins.a ?? first
      const b = pins.b ?? second ?? first
      const mid = midpoint(a, b)
      const lift = { x: mid.x, y: mid.y - 10 }
      return (
        <>
          <path d={`M${a.x},${a.y} L${a.x},${a.y - 10} L${b.x},${b.y - 10} L${b.x},${b.y}`} {...LEG} />
          <g transform={`rotate(${angle(a, b)} ${lift.x} ${lift.y})`}>
            {type === 'resistor' ? (
              <>
                <rect x={lift.x - 17} y={lift.y - 6} width="34" height="12" rx="5" fill="#e8d3a2" stroke="#9c7c3c" />
                {['#7c2d12', '#111827', '#b45309'].map((band, index) => (
                  <rect key={band} x={lift.x - 11 + index * 8} y={lift.y - 6} width="3.5" height="12" fill={band} />
                ))}
              </>
            ) : (
              <>
                <circle cx={lift.x} cy={lift.y} r="10" fill="#fde68a" stroke="#92400e" />
                <path
                  d={`M${lift.x - 6},${lift.y - 3} h4 v3 h4 v3 h4`}
                  fill="none"
                  stroke="#92400e"
                  strokeWidth="1.5"
                />
              </>
            )}
          </g>
          {props.value && (
            <text
              x={lift.x}
              y={lift.y - 11}
              fontSize="10"
              fontWeight="600"
              textAnchor="middle"
              fill="#374151"
              {...LABEL_HALO}
            >
              {props.value}
            </text>
          )}
        </>
      )
    }
    case 'button':
      return (
        <>
          <path d={`M${first.x},${first.y} L${last.x},${last.y}`} {...LEG} />
          <rect x={centre.x - 13} y={centre.y - 13} width="26" height="26" rx="4" fill="#374151" />
          <circle cx={centre.x} cy={centre.y} r="7" fill="#9ca3af" stroke="#111827" />
        </>
      )
    case 'buzzer':
      return (
        <>
          <path d={`M${first.x},${first.y} L${last.x},${last.y}`} {...LEG} />
          <circle cx={centre.x} cy={centre.y - 4} r="15" fill="#111827" />
          <circle cx={centre.x} cy={centre.y - 4} r="3" fill="#4b5563" />
          <text x={first.x - 10} y={first.y - 8} fontSize="12" fontWeight="700" fill="#b91c1c" {...LABEL_HALO}>
            +
          </text>
        </>
      )
    case 'potentiometer':
      return (
        <>
          {points.map((point) => (
            <path key={`${point.x}-${point.y}`} d={`M${point.x},${point.y} v-10`} {...LEG} />
          ))}
          <rect x={centre.x - 20} y={centre.y - 34} width="40" height="26" rx="4" fill="#1d4ed8" />
          <circle cx={centre.x} cy={centre.y - 21} r="8" fill="#e5e7eb" stroke="#111827" />
          <path d={`M${centre.x},${centre.y - 21} l4,-5`} stroke="#111827" strokeWidth="2" />
        </>
      )
    case 'ultrasonic':
      return (
        <>
          {points.map((point) => (
            <path key={`${point.x}-${point.y}`} d={`M${point.x},${point.y} v-12`} {...LEG} />
          ))}
          <rect x={first.x - 14} y={centre.y - 44} width={last.x - first.x + 28} height="32" rx="3" fill="#1e3a8a" />
          {[0.28, 0.72].map((share) => (
            <circle
              key={share}
              cx={first.x - 14 + (last.x - first.x + 28) * share}
              cy={centre.y - 28}
              r="10"
              fill="#cbd5e1"
              stroke="#475569"
            />
          ))}
        </>
      )
    default:
      return null
  }
}

/** Draws a part that sits beside the board. `at` is the centre of its box. */
export function drawOffBoardPart(
  type: ComponentType,
  at: Point,
  props: Record<string, string>,
): ReactNode {
  const box = (fill: string, label: string, width = 70) => (
    <>
      <rect x={at.x - width / 2} y={at.y - 22} width={width} height="44" rx="7" fill={fill} />
      <text x={at.x} y={at.y + 4} fontSize="11" fontWeight="600" textAnchor="middle" fill="white">
        {label}
      </text>
    </>
  )
  switch (type) {
    case 'battery':
      return (
        <>
          <rect x={at.x - 38} y={at.y - 20} width="76" height="40" rx="7" fill="#1f2937" />
          <rect x={at.x - 34} y={at.y - 16} width="68" height="32" rx="4" fill="#f59e0b" />
          <rect x={at.x + 38} y={at.y - 7} width="5" height="14" rx="2" fill="#1f2937" />
          <text x={at.x - 24} y={at.y + 5} fontSize="14" fontWeight="700" textAnchor="middle" fill="#7f1d1d">
            +
          </text>
          <text x={at.x} y={at.y + 4.5} fontSize="12" fontWeight="700" textAnchor="middle" fill="#111827">
            {props.value ?? 'Battery'}
          </text>
          <text x={at.x + 24} y={at.y + 5} fontSize="14" fontWeight="700" textAnchor="middle" fill="#111827">
            −
          </text>
        </>
      )
    case 'arduino_uno':
      return box('#0f766e', 'Arduino Uno', 96)
    case 'servo':
      return box('#2563eb', 'Servo')
    case 'dc_motor':
      return box('#6b7280', 'Motor')
    default:
      return null
  }
}
