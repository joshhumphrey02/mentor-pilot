import { useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { Loader2Icon } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useForm } from 'react-hook-form'
import type { z } from 'zod'

import { FormAlert, TextField } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { meQueryOptions, useResendVerification, useVerifyEmail } from '@/features/auth/api'
import { AuthShell, linkClass } from '@/features/auth/components/auth-shell'
import { CheckInbox } from '@/features/auth/components/check-inbox'
import { needsOnboarding } from '@/features/auth/guards'
import { emailOnlySchema } from '@/features/auth/schemas'
import { errorMessage } from '@/lib/api/errors'
import { zodResolver } from '@/lib/zod-resolver'

export const Route = createFileRoute('/_auth/verify-email')({
  validateSearch: (search: Record<string, unknown>): { token?: string } => ({
    token: typeof search.token === 'string' ? search.token : undefined,
  }),
  component: VerifyEmailPage,
})

function VerifyEmailPage() {
  const { token } = Route.useSearch()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const verify = useVerifyEmail()
  const started = useRef(false)
  const { mutateAsync } = verify

  useEffect(() => {
    // The link is single-use, so it must be submitted exactly once even though
    // React runs effects twice in development.
    if (!token || started.current) return
    started.current = true
    mutateAsync(token)
      .then((user) => navigate({ to: needsOnboarding(user) ? '/onboarding' : '/app', replace: true }))
      .catch(async () => {
        // An already-used link is fine if it was this browser that used it.
        const user = await queryClient.fetchQuery(meQueryOptions)
        if (user) await navigate({ to: needsOnboarding(user) ? '/onboarding' : '/app', replace: true })
      })
  }, [token, mutateAsync, navigate, queryClient])

  if (token && !verify.isError) {
    return (
      <AuthShell title="Confirming your email">
        <p role="status" className="flex items-center gap-3 text-muted-foreground">
          <Loader2Icon aria-hidden="true" className="size-5 animate-spin" />
          Just a moment…
        </p>
      </AuthShell>
    )
  }

  return (
    <AuthShell
      title={token ? "That link didn't work" : 'Confirm your email'}
      subtitle={
        token
          ? 'It may have expired or been used already. We can send you a fresh one.'
          : 'Enter your email and we’ll send you a new confirmation link.'
      }
      footer={
        <>
          Already confirmed? <Link className={linkClass} to="/login">Log in</Link>
        </>
      }
    >
      <ResendForm />
    </AuthShell>
  )
}

function ResendForm() {
  const resend = useResendVerification()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof emailOnlySchema>>({ resolver: zodResolver(emailOnlySchema) })

  if (resend.isSuccess) return <CheckInbox email={resend.variables} />

  return (
    <form
      onSubmit={handleSubmit(({ email }) => resend.mutate(email))}
      noValidate
      className="grid gap-4"
    >
      {resend.error && <FormAlert>{errorMessage(resend.error)}</FormAlert>}
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
      <Button type="submit" size="touch" disabled={resend.isPending} className="mt-2 w-full">
        {resend.isPending ? 'Sending…' : 'Send a new link'}
      </Button>
    </form>
  )
}
