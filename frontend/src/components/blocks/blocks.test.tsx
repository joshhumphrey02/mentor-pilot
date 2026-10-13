import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Block } from '@/features/chat/api'
import { WorkspaceContext, type WorkspaceValue } from '@/features/chat/workspace-context'
import { json, mockApi } from '@/test/app'

import { BlockRenderer } from './block-renderer'

afterEach(() => vi.unstubAllGlobals())

function show(block: Block, workspace: Partial<WorkspaceValue> = {}) {
  const send = vi.fn()
  const value: WorkspaceValue = {
    projectId: 'p1',
    currentStage: 'problem_discovery',
    send,
    busy: false,
    ...workspace,
  }
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <WorkspaceContext value={value}>
        <BlockRenderer block={block} />
      </WorkspaceContext>
    </QueryClientProvider>,
  )
  return { send }
}

const idea = {
  title: 'Solar phone charger',
  problem: 'Phones die during load-shedding.',
  field: 'Energy',
  difficulty: 3,
  cost_min_zar: 150,
  cost_max_zar: 400,
  materials: ['solar panel', 'USB module'],
  time_needed: '3 weeks',
  why_judges_like_it: 'A real local problem.',
  safety_level: 'medium' as const,
  safety_note: 'Do not short the battery.',
}

describe('idea cards', () => {
  it('shows each idea with its cost, difficulty and safety level', () => {
    show({ type: 'idea_cards', ideas: [idea, { ...idea, title: 'Water filter', safety_level: 'low' }] })

    const card = screen.getByRole('heading', { name: 'Solar phone charger' }).closest('article')!
    expect(within(card).getByText(/R\s?150 – R\s?400/)).toBeInTheDocument()
    expect(within(card).getByText('Difficulty 3 out of 5')).toBeInTheDocument()
    expect(within(card).getByText('Take care')).toBeInTheDocument()
    expect(within(card).getByText(/Do not short the battery/)).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(2)
  })

  it('speaks for the learner when a button is tapped', async () => {
    const { send } = show({ type: 'idea_cards', ideas: [idea] })

    await userEvent.click(screen.getByRole('button', { name: 'Choose this' }))
    await userEvent.click(screen.getByRole('button', { name: 'Explore' }))

    expect(send).toHaveBeenNthCalledWith(1, 'I choose “Solar phone charger”.')
    expect(send).toHaveBeenNthCalledWith(2, 'Tell me more about “Solar phone charger”.')
  })

  it('holds its buttons while the mentor is replying', () => {
    show({ type: 'idea_cards', ideas: [idea] }, { busy: true })

    expect(screen.getByRole('button', { name: 'Choose this' })).toBeDisabled()
  })
})

describe('comparison table', () => {
  it('lines each value up with its option', () => {
    show({
      type: 'comparison_table',
      title: 'Your shortlist',
      options: ['Charger', 'Filter'],
      rows: [
        { criterion: 'Cost', values: ['R400', 'R120'] },
        { criterion: 'Time', values: ['3 weeks', '2 weeks'] },
      ],
    })

    const row = screen.getByRole('row', { name: /Cost/ })
    expect(within(row).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['R400', 'R120'])
    expect(screen.getByRole('columnheader', { name: 'Filter' })).toBeInTheDocument()
  })
})

describe('bill of materials', () => {
  it('shows line totals, substitutes and the overall total', () => {
    show({
      type: 'bom_table',
      title: 'Bill of materials',
      total_zar: 17.5,
      items: [
        { name: 'LED', quantity: 5, unit_price_zar: 2.5, where_to_get: 'electronics shop', substitute: '' },
        { name: 'Cardboard', quantity: 1, unit_price_zar: 0, where_to_get: '', substitute: 'a cereal box' },
      ],
    })

    expect(screen.getByText(/R\s?12,50$/)).toBeInTheDocument()
    expect(screen.getByText(/R\s?2,50 each · electronics shop/)).toBeInTheDocument()
    expect(screen.getByText('Free')).toBeInTheDocument()
    expect(screen.getByText('a cereal box')).toBeInTheDocument()
    expect(screen.getByText(/R\s?17,50$/)).toBeInTheDocument()
  })
})

describe('quiz', () => {
  const quiz: Block = {
    type: 'quiz',
    title: 'Quick check',
    questions: [
      {
        question: 'Which variable do you change on purpose?',
        options: ['Independent', 'Dependent'],
        correct_index: 0,
        explanation: 'The independent variable is the one you choose to change.',
      },
      {
        question: 'Why repeat a trial?',
        options: ['To use more materials', 'To check the result is reliable'],
        correct_index: 1,
        explanation: 'Repeats show whether a result happens every time.',
      },
    ],
  }

  it('gives feedback after each answer and a score at the end', async () => {
    const { send } = show(quiz)

    expect(screen.getByText('Question 1 of 2')).toBeInTheDocument()
    expect(screen.queryByText(/independent variable is the one/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Dependent' }))
    expect(screen.getByText('Not quite.')).toBeInTheDocument()
    expect(screen.getByText(/independent variable is the one/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Independent/ })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Next question' }))
    await userEvent.click(screen.getByRole('button', { name: 'To check the result is reliable' }))
    expect(screen.getByText('That’s right.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'See my score' }))
    expect(screen.getByText('1 out of 2')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Tell my mentor' }))
    expect(send).toHaveBeenCalledWith('I got 1 out of 2 on the quick check.')
  })
})

describe('stage transition', () => {
  const card: Block = {
    type: 'stage_transition',
    from_stage: 'problem_discovery',
    to_stage: 'idea_development',
    from_title: 'Problem Discovery',
    to_title: 'Idea Development',
    summary: 'You found a real problem.',
  }

  it('asks the learner to confirm, then moves the project and tells the mentor', async () => {
    let body: unknown
    const { count } = mockApi({
      'POST /api/v1/projects/p1/stages/advance': async (request) => {
        body = await request.json()
        return json({ id: 'p1', current_stage: 'idea_development' })
      },
    })
    const { send } = show(card)

    await userEvent.click(screen.getByRole('button', { name: /Yes, move on/ }))

    await waitFor(() => expect(send).toHaveBeenCalledWith("I'm ready for Idea Development."))
    expect(body).toEqual({ from_stage: 'problem_discovery' })
    expect(count('POST /api/v1/projects/p1/stages/advance')).toBe(1)
  })

  it('lets the learner say not yet without changing anything', async () => {
    const { count } = mockApi()
    const { send } = show(card)

    await userEvent.click(screen.getByRole('button', { name: 'Not yet' }))

    expect(send).toHaveBeenCalledWith('Not yet. I want to keep working on Problem Discovery.')
    expect(count('POST /api/v1/projects/p1/stages/advance')).toBe(0)
  })

  it('becomes a celebration once the project has moved on', () => {
    show(card, { currentStage: 'idea_development' })

    expect(screen.getByRole('heading', { name: 'Problem Discovery complete' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /move on/ })).not.toBeInTheDocument()
  })
})

describe('checklist', () => {
  const stages = [
    {
      key: 'problem_discovery',
      position: 1,
      title: 'Problem Discovery',
      goal: 'Find a real problem.',
      status: 'active',
      handoff: false,
      checklist: [
        { key: 'observations', label: 'List three problems', done: true, note: 'Taps, litter, power' },
        { key: 'chosen_problem', label: 'Pick one problem', done: false, note: '' },
      ],
    },
  ]

  it('shows live progress and lets the learner tick an item', async () => {
    let body: unknown
    mockApi({
      'GET /api/v1/projects/p1/stages': () => json(stages),
      'PUT /api/v1/projects/p1/stages/problem_discovery/checklist/chosen_problem': async (request) => {
        body = await request.json()
        return json(stages)
      },
    })
    show({ type: 'checklist', stage_key: 'problem_discovery' })

    expect(await screen.findByText('1 of 2')).toBeInTheDocument()
    expect(screen.getByText('Taps, litter, power')).toBeInTheDocument()
    const box = screen.getByRole('checkbox', { name: /Pick one problem/ })
    await userEvent.click(box)

    await waitFor(() => expect(body).toEqual({ done: true }))
  })
})

describe('experiment plan', () => {
  it('lays out the variables and a blank data table', () => {
    show({
      type: 'experiment_plan',
      title: 'Does fertiliser change plant height?',
      independent_variable: 'Type of fertiliser',
      dependent_variable: 'Plant height in cm, measured with a ruler',
      controlled_variables: ['Same pot size', 'Same amount of water'],
      trials: 3,
      data_table: { columns: ['Trial', 'Height (cm)'], rows: 3 },
    })

    expect(screen.getByText('Type of fertiliser')).toBeInTheDocument()
    expect(screen.getByText('Repeat each test 3 times.')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Height (cm)' })).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(4)
  })
})

describe('chart', () => {
  it('offers the same numbers as a table', async () => {
    show({
      type: 'chart',
      chart_type: 'bar',
      title: 'Plant height by fertiliser',
      x_label: 'Fertiliser',
      y_label: 'Height (cm)',
      series: [{ name: 'Height', points: [{ x: 'None', y: 4 }, { x: 'Compost', y: 9.5 }] }],
    })

    expect(screen.getByText('Plant height by fertiliser')).toBeInTheDocument()
    const row = screen.getByRole('row', { name: /Compost/, hidden: true })
    expect(within(row).getByText('9.5')).toBeInTheDocument()
  })
})

describe('image gallery', () => {
  it('lazy-loads thumbnails with alt text and shows the credit in the lightbox', async () => {
    show({
      type: 'image_gallery',
      query: 'breadboard',
      images: [
        {
          url: 'https://upload.example/full.jpg',
          thumbnail_url: 'https://upload.example/thumb.jpg',
          title: 'Breadboard',
          source_url: 'https://commons.example/File:Breadboard.jpg',
          author: 'Jane Doe',
          license: 'CC BY-SA 4.0',
          width: 640,
          height: 480,
        },
      ],
    })

    const thumbnail = screen.getByRole('img', { name: 'Breadboard' })
    expect(thumbnail).toHaveAttribute('loading', 'lazy')
    await userEvent.click(thumbnail)

    expect(await screen.findByText('Jane Doe · CC BY-SA 4.0')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /View source and licence/ })).toHaveAttribute(
      'href',
      'https://commons.example/File:Breadboard.jpg',
    )
  })
})

describe('video cards', () => {
  it('loads nothing from YouTube until a card is tapped', async () => {
    show({
      type: 'video_cards',
      query: 'breadboards',
      videos: [{ video_id: 'abc123', title: 'How a breadboard works', channel: 'Science Class', thumbnail_url: '' }],
    })

    expect(document.querySelector('iframe')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /How a breadboard works/ }))

    const frame = await waitFor(() => {
      const found = document.querySelector('iframe')
      expect(found).not.toBeNull()
      return found!
    })
    expect(frame.getAttribute('src')).toContain('https://www.youtube-nocookie.com/embed/abc123')
  })
})

describe('unknown blocks', () => {
  it('are skipped instead of crashing an older app', () => {
    const { container } = render(
      <BlockRenderer block={{ type: 'hologram', text: 'from the future' } as unknown as Block} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
