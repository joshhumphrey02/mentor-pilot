import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { DownloadIcon, LogOutIcon, MonitorIcon, MoonIcon, SunIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { TextField } from '@/components/form/fields'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { useLogout, useUpdateProfile, useUser } from '@/features/auth/api'
import { nameSchema } from '@/features/auth/schemas'
import { DeleteAccount } from '@/features/profile/delete-account'
import { errorMessage } from '@/lib/api/errors'
import { cn } from '@/lib/utils'
import { zodResolver } from '@/lib/zod-resolver'
import { type Theme, useThemeStore } from '@/stores/theme'

export const Route = createFileRoute('/app/profile')({ component: ProfilePage })

const THEMES: { value: Theme; label: string; icon: typeof SunIcon }[] = [
  { value: 'light', label: 'Light', icon: SunIcon },
  { value: 'dark', label: 'Dark', icon: MoonIcon },
  { value: 'system', label: 'System', icon: MonitorIcon },
]

const profileSchema = z.object({ full_name: nameSchema })

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || '?'
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-soft">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="mt-4 grid gap-4">{children}</div>
    </section>
  )
}

function ProfilePage() {
  const user = useUser()
  const navigate = useNavigate()
  const logout = useLogout()
  const update = useUpdateProfile()
  const theme = useThemeStore((state) => state.theme)
  const setTheme = useThemeStore((state) => state.setTheme)
  const profile = user.student_profile

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: user.full_name },
  })

  const facts = [
    ['School', profile?.school?.name],
    ['Grade', profile?.grade ? `Grade ${profile.grade}` : null],
    ['Province', profile?.province],
  ].filter((fact): fact is [string, string] => Boolean(fact[1]))

  return (
    <div className="grid gap-6">
      <header className="flex items-center gap-4">
        <Avatar className="size-14">
          <AvatarFallback className="bg-secondary font-heading text-lg font-semibold text-secondary-foreground">
            {initials(user.full_name)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold">{user.full_name}</h1>
          <p className="truncate text-muted-foreground">{user.email}</p>
        </div>
      </header>

      <Section title="Your details">
        <form
          noValidate
          className="grid gap-4"
          onSubmit={handleSubmit(async (values) => {
            try {
              const saved = await update.mutateAsync(values)
              reset({ full_name: saved.full_name })
              toast.success('Saved')
            } catch (error) {
              toast.error(errorMessage(error))
            }
          })}
        >
          <TextField
            label="Name"
            autoComplete="name"
            error={errors.full_name?.message}
            {...register('full_name')}
          />
          {isDirty && (
            <Button type="submit" size="touch" disabled={update.isPending} className="justify-self-start">
              {update.isPending ? 'Saving…' : 'Save changes'}
            </Button>
          )}
        </form>
        {facts.length > 0 && (
          <dl className="grid gap-3 border-t pt-4 text-sm sm:grid-cols-3">
            {facts.map(([label, value]) => (
              <div key={label}>
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </Section>

      <Section title="Appearance">
        <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-2">
          {THEMES.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={theme === value}
              onClick={() => setTheme(value)}
              className={cn(
                'flex h-11 items-center justify-center gap-2 rounded-xl border text-sm font-medium transition-colors',
                theme === value
                  ? 'border-primary bg-secondary text-secondary-foreground'
                  : 'hover:border-primary',
              )}
            >
              <Icon aria-hidden="true" className="size-4" />
              {label}
            </button>
          ))}
        </div>
      </Section>

      <Section title="Your data">
        <p className="text-sm text-muted-foreground">
          You can download everything we hold about you, or delete your account, at any time. See
          the{' '}
          <Link to="/privacy" className="font-medium text-primary underline-offset-4 hover:underline">
            privacy notice
          </Link>
          .
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button asChild variant="outline" size="touch">
            <a href="/api/v1/users/me/export" download>
              <DownloadIcon data-icon="inline-start" />
              Download my data
            </a>
          </Button>
          <DeleteAccount />
        </div>
      </Section>

      <Button
        variant="outline"
        size="touch"
        disabled={logout.isPending}
        onClick={async () => {
          await logout.mutateAsync().catch(() => undefined)
          await navigate({ to: '/login' })
        }}
      >
        <LogOutIcon data-icon="inline-start" />
        Log out
      </Button>
    </div>
  )
}
