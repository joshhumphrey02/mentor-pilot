import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import type { z } from 'zod'

import { FormAlert, PasswordField, TextField } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { useLogin, useResendVerification } from '@/features/auth/api'
import { AuthShell, linkClass } from '@/features/auth/components/auth-shell'
import { GoogleButton } from '@/features/auth/components/google-button'
import { needsOnboarding, requireGuest, safeRedirect } from '@/features/auth/guards'
import { loginSchema } from '@/features/auth/schemas'
import { errorCode, errorMessage } from '@/lib/api/errors'
import { zodResolver } from '@/lib/zod-resolver'

interface LoginSearch {
  redirect?: string
  error?: string
}

export const Route = createFileRoute('/_auth/login')({
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    redirect: typeof search.redirect === 'string' ? search.redirect : undefined,
    error: typeof search.error === 'string' ? search.error : undefined,
  }),
  beforeLoad: requireGuest,
  component: LoginPage,
})

type LoginValues = z.infer<typeof loginSchema>

function LoginPage() {
  const search = Route.useSearch()
  const navigate = useNavigate()
  const login = useLogin()
  const resend = useResendVerification()
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  const onSubmit = handleSubmit(async (values) => {
    resend.reset()
    const user = await login.mutateAsync(values).catch(() => null)
    if (!user) return
    const target = safeRedirect(search.redirect)
    if (needsOnboarding(user)) await navigate({ to: '/onboarding' })
    else if (target) await navigate({ href: target })
    else await navigate({ to: '/app' })
  })

  const unverified = errorCode(login.error) === 'email_not_verified'

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Log in to pick up your project where you left off."
      footer={
        <>
          New here? <Link className={linkClass} to="/register">Create an account</Link>
        </>
      }
    >
      <GoogleButton label="Continue with Google" />

      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        {search.error === 'google_failed' && !login.error && (
          <FormAlert>
            We couldn't sign you in with Google. Try again, or use your email and password.
          </FormAlert>
        )}
        {login.error && !unverified && <FormAlert>{errorMessage(login.error)}</FormAlert>}
        {unverified && (
          <FormAlert tone="info">
            <p>{errorMessage(login.error)}</p>
            {resend.isSuccess ? (
              <p className="mt-1.5 font-medium">We've sent a new link.</p>
            ) : (
              <button
                type="button"
                className="mt-1.5 font-semibold underline underline-offset-4"
                disabled={resend.isPending}
                onClick={() => resend.mutate(getValues('email'))}
              >
                {resend.isPending ? 'Sending…' : 'Send the link again'}
              </button>
            )}
          </FormAlert>
        )}

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
        <div className="grid gap-2">
          <PasswordField
            label="Password"
            autoComplete="current-password"
            error={errors.password?.message}
            {...register('password')}
          />
          <p className="text-right text-sm">
            <Link className={linkClass} to="/forgot-password">Forgot your password?</Link>
          </p>
        </div>

        <Button type="submit" size="touch" disabled={login.isPending} className="mt-2 w-full">
          {login.isPending ? 'Logging in…' : 'Log in'}
        </Button>
      </form>
    </AuthShell>
  )
}
