import { useQuery } from '@tanstack/react-query'
import { CheckIcon, PlusIcon, SchoolIcon } from 'lucide-react'
import { useState } from 'react'

import { CONTROL_CLASS, TextField } from '@/components/form/fields'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { schoolSearchQueryOptions } from '@/features/auth/api'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { cn } from '@/lib/utils'

export interface SchoolChoice {
  mode: 'search' | 'new' | 'none'
  schoolId: string | null
  name: string
  town: string
}

interface SchoolPickerProps {
  value: SchoolChoice
  onChange: (value: SchoolChoice) => void
  error?: string
}

const linkButton = 'text-sm font-medium text-primary underline-offset-4 hover:underline'

/** Search for a school, add one that is missing, or say you are not at one. */
export function SchoolPicker({ value, onChange, error }: SchoolPickerProps) {
  const [query, setQuery] = useState('')
  const [selectedName, setSelectedName] = useState('')
  const term = useDebouncedValue(query.trim(), 250)
  const search = useQuery({ ...schoolSearchQueryOptions(term), enabled: term.length >= 2 })

  if (value.mode === 'none') {
    return (
      <div className="rounded-xl border bg-muted/50 p-4 text-sm">
        <p>No problem: you can add a school later in your profile.</p>
        <button
          type="button"
          className={cn(linkButton, 'mt-2')}
          onClick={() => onChange({ ...value, mode: 'search' })}
        >
          Actually, I am at a school
        </button>
      </div>
    )
  }

  if (value.mode === 'new') {
    return (
      <div className="grid gap-4">
        <TextField
          label="School name"
          autoComplete="organization"
          value={value.name}
          error={error}
          onChange={(event) => onChange({ ...value, name: event.target.value })}
        />
        <TextField
          label="Town or suburb"
          hint="Optional. Helps us tell schools with similar names apart."
          value={value.town}
          onChange={(event) => onChange({ ...value, town: event.target.value })}
        />
        <button
          type="button"
          className={cn(linkButton, 'justify-self-start')}
          onClick={() => onChange({ ...value, mode: 'search' })}
        >
          Search for my school instead
        </button>
      </div>
    )
  }

  const results = search.data ?? []
  const startAdding = () =>
    onChange({ mode: 'new', schoolId: null, name: query.trim(), town: value.town })

  return (
    <div className="grid gap-2">
      <Label htmlFor="school-search" className="text-sm font-medium">
        Your school
      </Label>

      {value.schoolId ? (
        <div className="flex items-center gap-3 rounded-xl border border-primary bg-secondary px-3.5 py-3 text-secondary-foreground">
          <CheckIcon aria-hidden="true" className="size-5 shrink-0" />
          <span className="min-w-0 flex-1 truncate font-medium">{selectedName}</span>
          <button
            type="button"
            className={linkButton}
            onClick={() => onChange({ ...value, schoolId: null })}
          >
            Change
          </button>
        </div>
      ) : (
        <>
          <Input
            id="school-search"
            type="search"
            placeholder="Start typing your school's name"
            autoComplete="off"
            value={query}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'school-error' : undefined}
            onChange={(event) => setQuery(event.target.value)}
            className={CONTROL_CLASS}
          />
          {term.length >= 2 && (
            <ul aria-label="Matching schools" className="grid gap-1.5">
              {results.map((school) => (
                <li key={school.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedName(school.name)
                      onChange({ ...value, mode: 'search', schoolId: school.id })
                    }}
                    className="flex min-h-11 w-full items-center gap-3 rounded-xl border bg-card px-3.5 py-2 text-left hover:border-primary"
                  >
                    <SchoolIcon aria-hidden="true" className="size-5 shrink-0 text-muted-foreground" />
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{school.name}</span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {[school.town, school.province].filter(Boolean).join(', ')}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
              <li>
                <button
                  type="button"
                  onClick={startAdding}
                  className="flex min-h-11 w-full items-center gap-3 rounded-xl border border-dashed px-3.5 py-2 text-left font-medium text-primary hover:border-primary"
                >
                  <PlusIcon aria-hidden="true" className="size-5 shrink-0" />
                  {search.isFetching && results.length === 0
                    ? 'Searching…'
                    : `Add “${query.trim()}” as my school`}
                </button>
              </li>
            </ul>
          )}
        </>
      )}

      {error && (
        <p id="school-error" role="alert" className="text-sm font-medium text-danger">
          {error}
        </p>
      )}
      {!value.schoolId && (
        <button
          type="button"
          className={cn(linkButton, 'justify-self-start')}
          onClick={() => onChange({ mode: 'none', schoolId: null, name: '', town: '' })}
        >
          I'm not at a school
        </button>
      )}
    </div>
  )
}
