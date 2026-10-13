import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { json, mockApi } from '@/test/app'

import CircuitView from './circuit-view'
import { LED_CIRCUIT } from './examples'
import { createBoard, describeHole, liveStrips, parseHole, PITCH, stripOf, toLayout } from './geometry'
import { LIBRARY, pinHelp } from './library'
import { buildSteps } from './steps'

afterEach(() => vi.unstubAllGlobals())

const correct = toLayout(LED_CIRCUIT)
const mistake = toLayout(LED_CIRCUIT.mistake!)

function show(block = LED_CIRCUIT, photos = false) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <CircuitView block={block} photos={photos} />
    </QueryClientProvider>,
  )
}

describe('breadboard geometry', () => {
  it('connects a column on one side of the gap, and nothing else', () => {
    expect(stripOf('A12')).toBe(stripOf('E12'))
    expect(stripOf('F12')).toBe(stripOf('J12'))
    expect(stripOf('E12')).not.toBe(stripOf('F12'))
    expect(stripOf('A12')).not.toBe(stripOf('A13'))
    expect(stripOf('+top:3')).toBe(stripOf('+top'))
    expect(stripOf('+top')).not.toBe(stripOf('+bottom'))
  })

  it('parses tie points and rails', () => {
    expect(parseHole('E12')).toEqual({ rail: null, row: 'E', column: 12 })
    expect(parseHole('-bottom:7')).toEqual({ rail: '-bottom', row: null, column: 7 })
    expect(parseHole('+top')).toEqual({ rail: '+top', row: null, column: null })
  })

  it('crops the board to the columns in use so holes stay large on a phone', () => {
    const board = createBoard([correct, mistake], true)

    expect(board.firstColumn).toBe(3)
    expect(board.lastColumn).toBeGreaterThanOrEqual(13)
    expect(board.columns.length).toBeGreaterThanOrEqual(12)
    expect(board.columns.length).toBeLessThan(30)
    expect(board.width).toBeLessThan(400)
  })

  it('never crops below a minimum width, and stays on the board', () => {
    const tiny = toLayout({
      components: [{ id: 'r', type: 'resistor', pins: { a: 'A29', b: 'A30' }, note: '' }],
    })
    const board = createBoard([tiny], false)

    expect(board.lastColumn).toBe(30)
    expect(board.columns.length).toBe(12)
  })

  it('places holes on a regular grid, with rails outside the rows', () => {
    const board = createBoard([correct], true)
    const a5 = board.point('A5')
    const b6 = board.point('B6')

    expect(b6.x - a5.x).toBe(PITCH)
    expect(b6.y - a5.y).toBe(PITCH)
    expect(board.point('+top', 5).x).toBe(a5.x)
    expect(board.point('+top').y).toBeLessThan(a5.y)
    expect(board.point('F5').y - board.point('E5').y).toBeGreaterThan(PITCH)
    expect(board.point('-bottom').y).toBeGreaterThan(board.point('J5').y)
  })

  it('knows which strips carry current', () => {
    const live = liveStrips(correct)

    expect(live).toEqual(new Set(['+top', '-top', 'top:5', 'top:10', 'top:11']))
  })

  it('names rails the way a person would', () => {
    expect(describeHole('+top:5')).toBe('the positive rail (top)')
    expect(describeHole('-bottom')).toBe('the negative rail (bottom)')
    expect(describeHole('E12')).toBe('E12')
  })
})

describe('component library', () => {
  it('explains every pin of every part', () => {
    for (const [type, info] of Object.entries(LIBRARY)) {
      expect(info.summary.length, type).toBeGreaterThan(40)
      expect(Object.keys(info.pins).length, type).toBeGreaterThan(0)
    }
    expect(pinHelp('led', 'anode')).toMatch(/long leg/i)
    expect(pinHelp('arduino_uno', 'D13')).toMatch(/Digital pins/)
    expect(pinHelp('arduino_uno', 'A0')).toMatch(/Analog pins/)
    expect(pinHelp('arduino_uno', 'GND')).toMatch(/Ground/)
  })
})

describe('build steps', () => {
  it('describes each part and wire from the wiring itself', () => {
    const steps = buildSteps(correct)

    expect(steps.map((step) => step.text)).toEqual([
      'Connect the Battery pack (3V): positive in the positive rail (top) and negative in the negative rail (top).',
      'Place the 100Ω Resistor: a in C5 and b in C10.',
      'Place the red LED: anode in D10 and cathode in D11.',
      'Add a red wire from the positive rail (top) to A5.',
      'Add a black wire from A11 to the negative rail (top).',
    ])
    expect(steps[2]?.note).toMatch(/long leg/i)
  })
})

describe('interactive breadboard', () => {
  it('draws every part as a labelled, focusable control', () => {
    show()

    const led = screen.getByRole('button', { name: /red LED\. anode in D10, cathode in D11/ })
    expect(led).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('button', { name: /100Ω Resistor\. a in C5, b in C10/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Battery pack/ })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /Lighting an LED: breadboard, wired correctly/ })).toBeInTheDocument()
  })

  it('reveals the metal strips and explains them', async () => {
    const { container } = show()
    const toggle = screen.getByRole('button', { name: 'Reveal inside' })
    expect(container.querySelector('.strips')).not.toHaveClass('is-revealed')

    await userEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(container.querySelector('.strips')).toHaveClass('is-revealed')
    expect(container.querySelectorAll('.strip-live')).toHaveLength(5)
    expect(screen.getByText(/each column of five holes sits on one metal strip/)).toBeInTheDocument()

    await userEvent.click(toggle)
    expect(container.querySelector('.strips')).not.toHaveClass('is-revealed')
  })

  it("switches to the common mistake, highlights it and explains why it fails", async () => {
    const { container } = show()
    expect(container.querySelector('.led-glow')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: "Don't" }))

    expect(screen.getByRole('radio', { name: "Don't" })).toBeChecked()
    expect(screen.getByText("Don't: Both LED legs in one column")).toBeInTheDocument()
    expect(screen.getByText(/skips the LED, which stays dark/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /anode in D10, cathode in E10/ })).toBeInTheDocument()
    expect(container.querySelectorAll('.hole-ring')).toHaveLength(2)
    expect(container.querySelector('.led-glow'), 'a miswired LED must not light').toBeNull()

    await userEvent.click(screen.getByRole('radio', { name: 'Do' }))
    expect(screen.queryByText(/Both LED legs in one column/)).not.toBeInTheDocument()
  })

  it('steps through the build one part at a time', async () => {
    const { container } = show()

    await userEvent.click(screen.getByRole('button', { name: 'Step through' }))

    expect(screen.getByText('Step 1 of 5')).toBeInTheDocument()
    // The same sentence is also in the collapsed text version, so look in the caption.
    expect(screen.getByText(/Connect the Battery pack/, { selector: '[aria-live]' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled()
    expect(container.querySelectorAll('.part.is-hidden')).toHaveLength(4)
    expect(container.querySelector('.led-glow'), 'not lit until it is finished').toBeNull()
    expect(screen.queryByRole('button', { name: /red LED/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Step 3 of 5')).toBeInTheDocument()
    expect(screen.getByText(/The long leg \(anode\) goes towards positive/)).toBeInTheDocument()
    expect(container.querySelector('.part.is-current')).toHaveAccessibleName(/red LED/)
    expect(container.querySelectorAll('.part.is-hidden')).toHaveLength(2)

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    expect(container.querySelector('.led-glow'), 'the finished circuit lights up').toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Stop stepping/ }))
    expect(screen.queryByText(/Step \d of 5/)).not.toBeInTheDocument()
    expect(container.querySelectorAll('.part.is-hidden')).toHaveLength(0)
  })

  it('offers the whole build as text', () => {
    show()

    const list = screen.getByText('Read the wiring as text').closest('details')!
    expect(within(list).getAllByRole('listitem', { hidden: true })).toHaveLength(5)
  })

  it('shows what a part is and what each leg does when tapped', async () => {
    show()

    await userEvent.click(screen.getByRole('button', { name: /red LED/ }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/only lets current flow one way/)).toBeInTheDocument()
    expect(within(dialog).getByText(/The long leg\. Goes towards positive/)).toBeInTheDocument()
    expect(within(dialog).getByText('in D10')).toBeInTheDocument()
  })

  it('opens part details from the keyboard', async () => {
    show()

    screen.getByRole('button', { name: /100Ω Resistor/ }).focus()
    await userEvent.keyboard('{Enter}')

    expect(await screen.findByRole('dialog')).toHaveTextContent('Limits how much current flows')
  })

  it('shows a credited photo of the real component', async () => {
    mockApi({
      'GET /api/v1/media/component-photo/led': () =>
        json({
          component: 'led',
          label: 'LED',
          image: {
            url: 'https://upload.example/led.jpg',
            thumbnail_url: 'https://upload.example/led-thumb.jpg',
            title: 'Red LED',
            source_url: 'https://commons.example/File:LED.jpg',
            author: 'Jane Doe',
            license: 'CC BY-SA 4.0',
          },
        }),
    })
    show(LED_CIRCUIT, true)

    await userEvent.click(screen.getByRole('button', { name: /red LED/ }))

    expect(await screen.findByRole('img', { name: 'A real LED' })).toHaveAttribute(
      'src',
      'https://upload.example/led-thumb.jpg',
    )
    expect(screen.getByText(/Jane Doe · CC BY-SA 4.0/)).toBeInTheDocument()
  })

  it('has no Do/Don’t switch when there is no mistake to show', () => {
    show({ ...LED_CIRCUIT, mistake: null })

    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reveal inside' })).toBeInTheDocument()
  })

  it('lists annotations under the board', () => {
    show()

    expect(screen.getByText('Long leg (anode) on the positive side')).toBeInTheDocument()
  })
})
