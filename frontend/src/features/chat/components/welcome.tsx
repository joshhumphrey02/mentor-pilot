import { LogoMark } from '@/components/brand/logo'

const STARTERS = [
  'I need help finding a project idea',
  'I already have an idea',
  'What do expo judges look for?',
]

/** The opening of an empty chat: who the mentor is, and three ways to begin. */
export function Welcome({ name, onPick }: { name: string; onPick: (text: string) => void }) {
  return (
    <div className="mx-auto max-w-md py-8 text-center">
      <LogoMark className="mx-auto size-12" />
      <h2 className="mt-5 text-2xl font-semibold">Hi {name}, I'm your mentor</h2>
      <p className="mt-2 text-muted-foreground">
        I'll guide you from a first idea all the way to the expo floor, one step at a time. The
        project stays yours: I'll ask questions, show you examples and give you honest feedback.
      </p>
      <ul className="mt-6 grid gap-2">
        {STARTERS.map((starter) => (
          <li key={starter}>
            <button
              type="button"
              onClick={() => onPick(starter)}
              className="min-h-11 w-full rounded-2xl border bg-card px-4 py-2.5 font-medium hover:border-primary hover:bg-secondary"
            >
              {starter}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
