import { cn } from '@/lib/utils'

import { HELP_TYPES, type HelpType } from './api'

interface HelpTypePickerProps {
  value: HelpType[]
  onChange: (value: HelpType[]) => void
  legend: string
}

/** Chips for the kinds of hands-on help. Used by learners asking and mentors offering. */
export function HelpTypePicker({ value, onChange, legend }: HelpTypePickerProps) {
  return (
    <fieldset>
      <legend className="text-sm font-medium">{legend}</legend>
      <div className="mt-2 flex flex-wrap gap-2">
        {(Object.entries(HELP_TYPES) as [HelpType, string][]).map(([key, label]) => {
          const selected = value.includes(key)
          return (
            <button
              key={key}
              type="button"
              aria-pressed={selected}
              onClick={() =>
                onChange(selected ? value.filter((item) => item !== key) : [...value, key])
              }
              className={cn(
                'min-h-11 rounded-full border px-4 text-sm font-medium transition-colors',
                selected
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'bg-card hover:border-primary',
              )}
            >
              {label}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
