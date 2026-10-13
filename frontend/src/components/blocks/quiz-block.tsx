import { CheckIcon, XIcon } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { useWorkspace } from '@/features/chat/workspace-context'
import type { Schemas } from '@/lib/api/client'
import { cn } from '@/lib/utils'

/** A quick check: one question at a time, with the explanation after each answer. */
export function QuizBlock({ block }: { block: Schemas['QuizBlock'] }) {
  const workspace = useWorkspace()
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<number[]>([])
  const [reported, setReported] = useState(false)
  const total = block.questions.length
  const question = block.questions[index]
  const chosen = answers[index]
  const answered = chosen !== undefined
  const score = answers.filter((answer, at) => answer === block.questions[at]?.correct_index).length

  if (!question) {
    return (
      <section aria-label={block.title} className="rounded-2xl border bg-card p-4 shadow-soft">
        <h3 className="font-heading text-lg font-semibold">{block.title}</h3>
        <p role="status" className="mt-2 text-2xl font-semibold">
          {score} out of {total}
        </p>
        <p className="mt-1 text-muted-foreground">
          {score === total
            ? 'Every one right. You know this.'
            : 'The ones you missed are the ones worth another look.'}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {workspace && !reported && (
            <Button
              size="touch"
              disabled={workspace.busy}
              onClick={() => {
                workspace.send(`I got ${score} out of ${total} on the quick check.`)
                setReported(true)
              }}
            >
              Tell my mentor
            </Button>
          )}
          <Button
            variant="outline"
            size="touch"
            onClick={() => {
              setAnswers([])
              setIndex(0)
            }}
          >
            Try again
          </Button>
        </div>
      </section>
    )
  }

  return (
    <section aria-label={block.title} className="rounded-2xl border bg-card p-4 shadow-soft">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-heading text-lg font-semibold">{block.title}</h3>
        <p className="shrink-0 text-sm text-muted-foreground">
          Question {index + 1} of {total}
        </p>
      </div>

      <fieldset className="mt-3">
        <legend className="font-medium">{question.question}</legend>
        <div className="mt-3 grid gap-2">
          {question.options.map((option, optionIndex) => {
            const correct = optionIndex === question.correct_index
            const picked = optionIndex === chosen
            return (
              <button
                key={option}
                type="button"
                disabled={answered}
                aria-pressed={picked}
                onClick={() =>
                  setAnswers((current) => {
                    const next = [...current]
                    next[index] = optionIndex
                    return next
                  })
                }
                className={cn(
                  'flex min-h-11 items-center gap-3 rounded-xl border px-3.5 py-2.5 text-left transition-colors',
                  !answered && 'hover:border-primary',
                  answered && correct && 'border-success bg-success-soft',
                  answered && picked && !correct && 'border-danger bg-danger-soft',
                  answered && !picked && !correct && 'opacity-60',
                )}
              >
                <span className="flex-1">{option}</span>
                {answered && correct && (
                  <CheckIcon aria-label="Correct answer" className="size-5 shrink-0 text-success" />
                )}
                {answered && picked && !correct && (
                  <XIcon aria-label="Your answer" className="size-5 shrink-0 text-danger" />
                )}
              </button>
            )
          })}
        </div>
      </fieldset>

      {answered && (
        <div role="status" className="mt-3 rounded-xl bg-muted p-3 text-sm">
          <p className="font-semibold">
            {chosen === question.correct_index ? 'That’s right.' : 'Not quite.'}
          </p>
          <p className="mt-1">{question.explanation}</p>
        </div>
      )}

      {answered && (
        <Button size="touch" className="mt-3" onClick={() => setIndex((value) => value + 1)}>
          {index + 1 === total ? 'See my score' : 'Next question'}
        </Button>
      )}
    </section>
  )
}
