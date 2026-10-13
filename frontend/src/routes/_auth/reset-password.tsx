import { createFileRoute, Link } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import type { z } from 'zod'

import { FormAlert, PasswordField } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { useResetPassword } from '@/features/auth/api'
import { AuthShell, linkClass } from '@/features/auth/components/auth-shell'
import { resetPasswordSchema } from '@/features/auth/schemas'
import { errorMessage } from '@/lib/api/errors'
import { zodResolver } from '@/lib/zod-resolver'

export const Route = createFileRoute('/_auth/reset-password')({
  validateSearch: (search: Record<string, unknown>): { token?: string } => ({
    token: typeof search.token === 'string' ? search.token : undefined,
  }),
  component: ResetPasswordPage,
})

function ResetPasswordPage() {
  const { token } = Route.useSearch()
  const reset = useResetPassword()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof resetPasswordSchema>>({ resolver: zodResolver(resetPasswordSchema) })

  if (!token) {
    return (
      <AuthShell title="This link isn't complete">
        <FormAlert>
          Open the link from your email again, or{' '}
          <Link className={linkClass} to="/forgot-password">request a new one</Link>.
        </FormAlert>
      </AuthShell>
    )
  }

  if (reset.isSuccess) {
    return (
      <AuthShell title="Password changed">
        <FormAlert tone="success">Your new password is saved.</FormAlert>
        <Button asChild size="touch" className="mt-6 w-full">
          <Link to="/login">Log in</Link>
        </Button>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Choose a new password">
      <form
        onSubmit={handleSubmit(({ password }) => reset.mutate({ token, password }))}
        noValidate
        className="grid gap-4"
      >
        {reset.error && (
          <FormAlert>
            {errorMessage(reset.error)}{' '}
            <Link className={linkClass} to="/forgot-password">Request a new link</Link>
          </FormAlert>
        )}
        <PasswordField
          label="New password"
          autoComplete="new-password"
          hint="At least 8 characters."
          error={errors.password?.message}
          {...register('password')}
        />
        <Button type="submit" size="touch" disabled={reset.isPending} className="mt-2 w-full">
          {reset.isPending ? 'Saving…' : 'Save new password'}
        </Button>
      </form>
    </AuthShell>
  )
}
