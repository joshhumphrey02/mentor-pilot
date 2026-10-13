import { createFileRoute, Link } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import type { z } from 'zod'

import { FormAlert, TextField } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { useForgotPassword } from '@/features/auth/api'
import { AuthShell, linkClass } from '@/features/auth/components/auth-shell'
import { CheckInbox } from '@/features/auth/components/check-inbox'
import { emailOnlySchema } from '@/features/auth/schemas'
import { errorMessage } from '@/lib/api/errors'
import { zodResolver } from '@/lib/zod-resolver'

export const Route = createFileRoute('/_auth/forgot-password')({ component: ForgotPasswordPage })

function ForgotPasswordPage() {
  const forgot = useForgotPassword()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof emailOnlySchema>>({ resolver: zodResolver(emailOnlySchema) })

  const footer = (
    <>
      Remembered it? <Link className={linkClass} to="/login">Back to log in</Link>
    </>
  )

  if (forgot.isSuccess) {
    return (
      <AuthShell title="Check your inbox" footer={footer}>
        <CheckInbox email={forgot.variables} />
      </AuthShell>
    )
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your email and we'll send you a link to choose a new one."
      footer={footer}
    >
      <form
        onSubmit={handleSubmit(({ email }) => forgot.mutate(email))}
        noValidate
        className="grid gap-4"
      >
        {forgot.error && <FormAlert>{errorMessage(forgot.error)}</FormAlert>}
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
        <Button type="submit" size="touch" disabled={forgot.isPending} className="mt-2 w-full">
          {forgot.isPending ? 'Sending…' : 'Send reset link'}
        </Button>
      </form>
    </AuthShell>
  )
}
