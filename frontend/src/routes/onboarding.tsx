import { createFileRoute, Link, redirect, useNavigate } from '@tanstack/react-router'
import { ArrowLeftIcon, ArrowRightIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Controller, useForm, useWatch } from 'react-hook-form'

import { Logo } from '@/components/brand/logo'
import { FormAlert, SelectField, TextField } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Progress } from '@/components/ui/progress'
import { type OnboardingInput, useCompleteOnboarding, useUser } from '@/features/auth/api'
import { needsOnboarding, requireUser } from '@/features/auth/guards'
import {
  GRADES,
  INTERESTS,
  isMinor,
  LANGUAGES,
  LEARNING_STYLES,
  PROVINCES,
} from '@/features/onboarding/options'
import {
  type LearningStyle,
  onboardingSchema,
  type OnboardingValues,
} from '@/features/onboarding/schema'
import { SchoolPicker } from '@/features/onboarding/school-picker'
import { errorMessage } from '@/lib/api/errors'
import { cn } from '@/lib/utils'
import { zodResolver } from '@/lib/zod-resolver'

export const Route = createFileRoute('/onboarding')({
  beforeLoad: async (args) => {
    const { user } = await requireUser(args)
    if (!needsOnboarding(user)) throw redirect({ to: '/app' })
  },
  component: OnboardingPage,
})

type FieldName = keyof OnboardingValues

const STEPS: { title: string; subtitle: string; fields: FieldName[] }[] = [
  {
    title: 'First, about you',
    subtitle: 'So your mentor knows who they are talking to.',
    fields: ['full_name', 'date_of_birth', 'guardian_email', 'guardian_consent'],
  },
  {
    title: 'Where do you learn?',
    subtitle: 'This helps us connect you with mentors and expos near you.',
    fields: ['school_id', 'school_name', 'province', 'grade'],
  },
  {
    title: 'What are you curious about?',
    subtitle: 'Pick as many as you like. Your mentor will suggest projects around them.',
    fields: ['interests'],
  },
  {
    title: 'How do you learn best?',
    subtitle: 'Your mentor will explain things this way first.',
    fields: ['learning_style', 'preferred_language', 'accept_privacy'],
  },
]

function toPayload(values: OnboardingValues): OnboardingInput {
  const minor = isMinor(values.date_of_birth)
  return {
    full_name: values.full_name.trim(),
    date_of_birth: values.date_of_birth,
    school_id: values.school_mode === 'search' ? values.school_id : null,
    new_school:
      values.school_mode === 'new'
        ? {
            name: values.school_name.trim(),
            province: values.province,
            town: values.school_town.trim() || null,
          }
        : null,
    education_level: 'high_school',
    grade: values.grade || null,
    province: values.province,
    interests: values.interests,
    // The schema has already checked this is one of the four styles.
    learning_style: values.learning_style as LearningStyle,
    preferred_language: values.preferred_language,
    guardian_consent: minor && values.guardian_consent,
    guardian_email: minor ? values.guardian_email.trim() : null,
    accept_privacy: values.accept_privacy,
  }
}

function OnboardingPage() {
  const user = useUser()
  const navigate = useNavigate()
  const complete = useCompleteOnboarding()
  const [step, setStep] = useState(0)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [today] = useState(() => new Date().toISOString().slice(0, 10))

  const {
    register,
    control,
    handleSubmit,
    trigger,
    setValue,
    formState: { errors },
  } = useForm<OnboardingValues>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      full_name: user.full_name,
      date_of_birth: '',
      guardian_email: '',
      guardian_consent: false,
      school_mode: 'search',
      school_id: null,
      school_name: '',
      school_town: '',
      province: 'Western Cape',
      grade: '',
      interests: [],
      learning_style: '',
      preferred_language: 'en',
      accept_privacy: false,
      needs_privacy: !user.privacy_accepted,
    },
  })

  const [dateOfBirth, schoolMode, schoolId, schoolName, schoolTown] = useWatch({
    control,
    name: ['date_of_birth', 'school_mode', 'school_id', 'school_name', 'school_town'],
  })
  const minor = isMinor(dateOfBirth)
  const current = STEPS[step]
  const isLast = step === STEPS.length - 1

  // Move focus to the new step's heading so screen-reader and keyboard users
  // are not left on a button that has just changed meaning.
  useEffect(() => {
    if (step > 0) headingRef.current?.focus()
  }, [step])

  if (!current) return null

  const next = async () => {
    if (await trigger(current.fields, { shouldFocus: true })) setStep((value) => value + 1)
  }

  const submit = handleSubmit(async (values) => {
    const saved = await complete.mutateAsync(toPayload(values)).catch(() => null)
    if (saved) await navigate({ to: '/app', replace: true })
  })

  return (
    <div className="flex min-h-dvh flex-col pt-safe">
      <header className="mx-auto flex h-16 w-full max-w-lg items-center justify-between px-safe">
        <Logo />
        <p className="text-sm font-medium text-muted-foreground" aria-live="polite">
          Step {step + 1} of {STEPS.length}
        </p>
      </header>
      <div className="mx-auto w-full max-w-lg px-safe">
        <Progress
          value={((step + 1) / STEPS.length) * 100}
          aria-label="Onboarding progress"
          className="h-1.5"
        />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault()
          void (isLast ? submit() : next())
        }}
        noValidate
        className="mx-auto flex w-full max-w-lg flex-1 flex-col px-safe"
      >
        <main id="main" className="flex-1 pt-8 pb-6">
          <h1 ref={headingRef} tabIndex={-1} className="text-3xl font-semibold outline-none">
            {current.title}
          </h1>
          <p className="mt-2 text-muted-foreground">{current.subtitle}</p>

          <div className="mt-8 grid gap-5">
            {step === 0 && (
              <>
                <TextField
                  label="Your name"
                  autoComplete="name"
                  error={errors.full_name?.message}
                  {...register('full_name')}
                />
                <TextField
                  label="Date of birth"
                  type="date"
                  autoComplete="bday"
                  max={today}
                  hint="We use this to keep Mentor Pilot safe and right for your age."
                  error={errors.date_of_birth?.message}
                  {...register('date_of_birth')}
                />
                {minor && (
                  <div className="grid gap-4 rounded-2xl border bg-info-soft/60 p-4">
                    <p className="text-sm">
                      Because you're under 18, a parent, guardian or teacher needs to agree to you
                      using Mentor Pilot. We'll email them to let them know.
                    </p>
                    <TextField
                      label="Their email address"
                      type="email"
                      inputMode="email"
                      autoCapitalize="none"
                      spellCheck={false}
                      className="bg-background"
                      error={errors.guardian_email?.message}
                      {...register('guardian_email')}
                    />
                    <CheckboxRow
                      control={control}
                      name="guardian_consent"
                      error={errors.guardian_consent?.message}
                    >
                      I've asked them, and they agree.
                    </CheckboxRow>
                  </div>
                )}
              </>
            )}

            {step === 1 && (
              <>
                <SchoolPicker
                  value={{
                    mode: schoolMode,
                    schoolId,
                    name: schoolName,
                    town: schoolTown,
                  }}
                  error={errors.school_id?.message ?? errors.school_name?.message}
                  onChange={(choice) => {
                    setValue('school_mode', choice.mode)
                    setValue('school_id', choice.schoolId)
                    setValue('school_name', choice.name)
                    setValue('school_town', choice.town)
                    if (errors.school_id || errors.school_name) {
                      void trigger(['school_id', 'school_name'])
                    }
                  }}
                />
                <div className="grid grid-cols-2 gap-4">
                  <SelectField
                    label="Province"
                    error={errors.province?.message}
                    {...register('province')}
                  >
                    {PROVINCES.map((province) => (
                      <option key={province}>{province}</option>
                    ))}
                  </SelectField>
                  <SelectField label="Grade" {...register('grade')}>
                    <option value="">Not sure / other</option>
                    {GRADES.map((grade) => (
                      <option key={grade} value={grade}>
                        Grade {grade}
                      </option>
                    ))}
                  </SelectField>
                </div>
              </>
            )}

            {step === 2 && (
              <Controller
                control={control}
                name="interests"
                render={({ field }) => (
                  <fieldset>
                    <legend className="sr-only">Your interests</legend>
                    <div className="flex flex-wrap gap-2.5">
                      {INTERESTS.map(({ value, label, icon: Icon }) => {
                        const selected = field.value.includes(value)
                        return (
                          <button
                            key={value}
                            type="button"
                            aria-pressed={selected}
                            onClick={() =>
                              field.onChange(
                                selected
                                  ? field.value.filter((item) => item !== value)
                                  : [...field.value, value],
                              )
                            }
                            className={cn(
                              'inline-flex min-h-11 items-center gap-2 rounded-full border px-4 text-base font-medium transition-colors',
                              selected
                                ? 'border-primary bg-primary text-primary-foreground'
                                : 'bg-card hover:border-primary',
                            )}
                          >
                            <Icon aria-hidden="true" className="size-5" />
                            {label}
                          </button>
                        )
                      })}
                    </div>
                    {errors.interests && (
                      <p role="alert" className="mt-3 text-sm font-medium text-danger">
                        {errors.interests.message}
                      </p>
                    )}
                  </fieldset>
                )}
              />
            )}

            {step === 3 && (
              <>
                <fieldset>
                  <legend className="sr-only">How you learn best</legend>
                  <div className="grid gap-2.5 sm:grid-cols-2">
                    {LEARNING_STYLES.map((style) => (
                      <label
                        key={style.value}
                        className="flex min-h-11 cursor-pointer flex-col rounded-2xl border bg-card p-4 transition-colors has-checked:border-primary has-checked:bg-secondary has-focus-visible:ring-3 has-focus-visible:ring-ring/50"
                      >
                        <input
                          type="radio"
                          value={style.value}
                          className="sr-only"
                          {...register('learning_style')}
                        />
                        <span className="font-semibold">{style.label}</span>
                        <span className="text-sm text-muted-foreground">{style.description}</span>
                      </label>
                    ))}
                  </div>
                  {errors.learning_style && (
                    <p role="alert" className="mt-3 text-sm font-medium text-danger">
                      {errors.learning_style.message}
                    </p>
                  )}
                </fieldset>

                <SelectField
                  label="Language"
                  hint="Afrikaans and isiXhosa are on the way."
                  {...register('preferred_language')}
                >
                  {LANGUAGES.map((language) => (
                    <option key={language.value} value={language.value} disabled={!language.available}>
                      {language.label}
                      {language.available ? '' : ' (coming soon)'}
                    </option>
                  ))}
                </SelectField>

                {!user.privacy_accepted && (
                  <CheckboxRow
                    control={control}
                    name="accept_privacy"
                    error={errors.accept_privacy?.message}
                  >
                    I agree to how Mentor Pilot uses my information, as explained in the{' '}
                    <Link
                      to="/privacy"
                      target="_blank"
                      className="font-medium text-primary underline-offset-4 hover:underline"
                    >
                      privacy notice
                    </Link>
                    .
                  </CheckboxRow>
                )}

                {complete.error && <FormAlert>{errorMessage(complete.error)}</FormAlert>}
              </>
            )}
          </div>
        </main>

        {/* Sticky so the primary action stays within thumb reach on long steps. */}
        <footer className="sticky bottom-0 -mx-4 flex gap-3 border-t bg-background/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur">
          {step > 0 && (
            <Button
              type="button"
              variant="outline"
              size="touch"
              onClick={() => setStep((value) => value - 1)}
            >
              <ArrowLeftIcon data-icon="inline-start" />
              Back
            </Button>
          )}
          <Button type="submit" size="touch" disabled={complete.isPending} className="flex-1">
            {isLast ? (complete.isPending ? 'Saving…' : 'Meet your mentor') : 'Continue'}
            {!isLast && <ArrowRightIcon data-icon="inline-end" />}
          </Button>
        </footer>
      </form>
    </div>
  )
}

function CheckboxRow({
  control,
  name,
  error,
  children,
}: {
  control: ReturnType<typeof useForm<OnboardingValues>>['control']
  name: 'guardian_consent' | 'accept_privacy'
  error?: string
  children: React.ReactNode
}) {
  return (
    <div className="grid gap-1.5">
      <label className="flex items-start gap-3 text-sm">
        <Controller
          control={control}
          name={name}
          render={({ field }) => (
            <Checkbox
              checked={field.value}
              onCheckedChange={(checked) => field.onChange(checked === true)}
              onBlur={field.onBlur}
              ref={field.ref}
              aria-invalid={error ? true : undefined}
              className="mt-0.5 size-5 bg-background"
            />
          )}
        />
        <span>{children}</span>
      </label>
      {error && (
        <p role="alert" className="text-sm font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
