import { describeHole, type Layout, type Part } from './geometry'
import { LIBRARY } from './library'

export interface BuildStep {
  /** `component:<id>` or `wire:<index>`: which drawn element this step adds. */
  key: string
  text: string
  note: string
}

export function componentName(component: Part): string {
  const info = LIBRARY[component.type]
  const detail = component.props.color ?? component.props.value
  return detail && component.type !== 'battery'
    ? `${detail} ${info.label}`
    : `${info.label}${component.props.value ? ` (${component.props.value})` : ''}`
}

function listPins(component: Part): string {
  const parts = Object.entries(component.pins).map(
    ([pin, hole]) => `${pin} in ${describeHole(hole)}`,
  )
  if (parts.length <= 1) return parts.join('')
  return `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}`
}

/**
 * The build as a teacher would do it live: one part or wire at a time, in the
 * order the mentor listed them. The sentence for each step is generated from
 * the wiring itself, so the words can never disagree with the picture.
 */
export function buildSteps(layout: Layout): BuildStep[] {
  return [
    ...layout.components.map((component) => ({
      key: `component:${component.id}`,
      text: `${LIBRARY[component.type].offBoard ? 'Connect' : 'Place'} the ${componentName(component)}: ${listPins(component)}.`,
      note: component.note,
    })),
    ...layout.wires.map((wire, index) => ({
      key: `wire:${index}`,
      text: `Add a ${wire.color} wire from ${describeHole(wire.from)} to ${describeHole(wire.to)}.`,
      note: wire.note,
    })),
  ]
}
