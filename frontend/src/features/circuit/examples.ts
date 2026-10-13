import type { Schemas } from '@/lib/api/client'

/**
 * The reference circuit: lighting an LED from a battery pack, with the classic
 * beginner's mistake. Mirrors LED_CIRCUIT in backend/app/ai/tools/circuit.py.
 * Used for the landing-page demo and in tests.
 */
export const LED_CIRCUIT: Schemas['CircuitBlock'] = {
  type: 'circuit',
  title: 'Lighting an LED',
  components: [
    {
      id: 'battery',
      type: 'battery',
      pins: { positive: '+top', negative: '-top' },
      props: { value: '3V' },
      note: 'Two AA batteries give 3 volts: safe to touch and enough for an LED.',
    },
    {
      id: 'resistor',
      type: 'resistor',
      pins: { a: 'C5', b: 'C10' },
      props: { value: '100Ω' },
      note: 'The resistor limits the current so the LED does not burn out.',
    },
    {
      id: 'led',
      type: 'led',
      pins: { anode: 'D10', cathode: 'D11' },
      props: { color: 'red' },
      note: 'The long leg (anode) goes towards positive. Each leg has its own column.',
    },
  ],
  wires: [
    { from: '+top:5', to: 'A5', color: 'red', note: 'Positive rail to the resistor.' },
    { from: 'A11', to: '-top:11', color: 'black', note: 'Back to the negative rail.' },
  ],
  highlight: [],
  annotations: [{ at: 'D10', text: 'Long leg (anode) on the positive side' }],
  mistake: {
    title: 'Both LED legs in one column',
    explanation:
      'Column 10 is a single metal strip under the board, so both legs are joined together. The current takes the easy path through the strip and skips the LED, which stays dark. Reveal the inside of the board to see the strip.',
    components: [
      {
        id: 'battery',
        type: 'battery',
        pins: { positive: '+top', negative: '-top' },
        props: { value: '3V' },
        note: '',
      },
      { id: 'resistor', type: 'resistor', pins: { a: 'C5', b: 'C10' }, props: { value: '100Ω' }, note: '' },
      { id: 'led', type: 'led', pins: { anode: 'D10', cathode: 'E10' }, props: { color: 'red' }, note: '' },
    ],
    wires: [
      { from: '+top:5', to: 'A5', color: 'red', note: '' },
      { from: 'A10', to: '-top:10', color: 'black', note: '' },
    ],
    highlight: ['D10', 'E10'],
  },
}
