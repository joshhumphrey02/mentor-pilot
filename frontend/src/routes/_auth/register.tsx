import { createFileRoute, Link } from '@tanstack/react-router'
import { Controller, useForm } from 'react-hook-form'
import type { z } from 'zod'

import { FormAlert, PasswordField, TextField } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { useRegister } from '@/features/auth/api'
import { AuthShell, linkClass } from '@/features/auth/components/auth-shell'
import { CheckInbox } from '@/features/auth/components/check-inbox'
import { GoogleButton } from '@/features/auth/components/google-button'
import { requireGuest } from '@/features/auth/guards'
import { registerSchema } from '@/features/auth/schemas'
import { errorMessage } from '@/lib/api/errors'
import { zodResolver } from '@/lib/zod-resolver'

export const Route = createFileRoute('/_auth/register')({
  beforeLoad: requireGuest,
  component: RegisterPage,
})

// The checkbox starts unticked, so the form's input type is wider than the schema's output.
type RegisterInput = Omit<z.input<typeof registerSchema>, 'accept_privacy'> & {
  accept_privacy: boolean
}
type RegisterValues = z.output<typeof registerSchema>

function RegisterPage() {
  const signUp = useRegister()
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterInput, unknown, RegisterValues>({
    resolver: zodResolver(registerSchema) as never,
    defaultValues: { full_name: '', email: '', password: '', accept_privacy: false },
  })

  if (signUp.isSuccess) {
    return (
      <AuthShell title="Check your inbox" subtitle="One more step: confirm your email address.">
        <CheckInbox email={signUp.variables.email}>
          <p className="text-sm text-muted-foreground">
            Wrong address?{' '}
            <button
              type="button"
              className="font-medium text-primary underline-offset-4 hover:underline"
              onClick={() => signUp.reset()}
            >
              Go back
            </button>
          </p>
        </CheckInbox>
      </AuthShell>
    )
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Free to start. Your mentor is ready when you are."
      footer={
        <>
          Already have an account? <Link className={linkClass} to="/login">Log in</Link>
          <span className="mt-2 block">
            Want to help learners?{' '}
            <Link className={linkClass} to="/register-mentor">
              Become a mentor
            </Link>
          </span>
        </>
      }
    >
      <GoogleButton label="Sign up with Google" />

      <form
        onSubmit={handleSubmit((values) => signUp.mutate(values))}
        noValidate
        className="grid gap-4"
      >
        {signUp.error && <FormAlert>{errorMessage(signUp.error)}</FormAlert>}

        <TextField
          label="Your name"
          autoComplete="name"
          error={errors.full_name?.message}
          {...register('full_name')}
        />
        <TextField
          label="Email"
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          spellCheck={false}
          error={errors.email?.message}
          {...register('email')}
        />
        <PasswordField
          label="Password"
          autoComplete="new-password"
          hint="At least 8 characters. A short sentence works well."
          error={errors.password?.message}
          {...register('password')}
        />

        <div className="grid gap-1.5">
          <label className="flex items-start gap-3 text-sm">
            <Controller
              control={control}
              name="accept_privacy"
              render={({ field }) => (
                <Checkbox
                  checked={field.value}
                  onCheckedChange={(checked) => field.onChange(checked === true)}
                  onBlur={field.onBlur}
                  ref={field.ref}
                  aria-invalid={errors.accept_privacy ? true : undefined}
                  className="mt-0.5 size-5"
                />
              )}
            />
            <span>
              I agree to how Mentor Pilot uses my information, as explained in the{' '}
              <Link
                to="/privacy"
                target="_blank"
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                privacy notice
              </Link>
              .
            </span>
          </label>
          {errors.accept_privacy && (
            <p role="alert" className="text-sm font-medium text-danger">
              {errors.accept_privacy.message}
            </p>
          )}
        </div>

        <Button type="submit" size="touch" disabled={signUp.isPending} className="mt-2 w-full">
          {signUp.isPending ? 'Creating your account…' : 'Create account'}
        </Button>
      </form>
    </AuthShell>
  )
}
