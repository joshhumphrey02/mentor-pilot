import { EyeIcon, EyeOffIcon } from 'lucide-react'
import { type ComponentProps, type ReactNode, useId, useState } from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

// 44px tall with 16px text: comfortable to tap, and iOS does not zoom on focus.
export const CONTROL_CLASS = 'h-11 rounded-xl px-3.5 text-base md:text-base'

interface FieldShellProps {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string
  className?: string
  children: ReactNode
}

function FieldShell({ id, label, hint, error, className, children }: FieldShellProps) {
  return (
    <div className={cn('grid gap-1.5', className)}>
      <Label htmlFor={id} className="text-sm font-medium">
        {label}
      </Label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="text-sm font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

function describedBy(id: string, hint: unknown, error: unknown) {
  if (error) return `${id}-error`
  return hint ? `${id}-hint` : undefined
}

interface FieldProps {
  label: ReactNode
  hint?: ReactNode
  error?: string
  containerClassName?: string
}

export function TextField({
  label,
  hint,
  error,
  containerClassName,
  className,
  ...props
}: FieldProps & ComponentProps<'input'>) {
  const id = useId()
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} className={containerClassName}>
      <Input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        className={cn(CONTROL_CLASS, className)}
        {...props}
      />
    </FieldShell>
  )
}

export function PasswordField({
  label,
  hint,
  error,
  containerClassName,
  className,
  ...props
}: FieldProps & Omit<ComponentProps<'input'>, 'type'>) {
  const id = useId()
  const [visible, setVisible] = useState(false)
  const Icon = visible ? EyeOffIcon : EyeIcon
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} className={containerClassName}>
      <div className="relative">
        <Input
          id={id}
          type={visible ? 'text' : 'password'}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, hint, error)}
          className={cn(CONTROL_CLASS, 'pr-12', className)}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((value) => !value)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-xl text-muted-foreground hover:text-foreground"
        >
          <Icon aria-hidden="true" className="size-5" />
        </button>
      </div>
    </FieldShell>
  )
}

/**
 * A native <select>: on phones it opens the OS picker, which is easier to use
 * with a thumb than any custom dropdown.
 */
export function SelectField({
  label,
  hint,
  error,
  containerClassName,
  className,
  children,
  ...props
}: FieldProps & ComponentProps<'select'>) {
  const id = useId()
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} className={containerClassName}>
      <select
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        className={cn(
          'w-full appearance-none border border-input bg-transparent bg-[length:1rem] bg-[right_0.875rem_center] bg-no-repeat pr-10 outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive dark:bg-input/30',
          "bg-[url('data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23808799%22%20stroke-width%3D%222.5%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')]",
          CONTROL_CLASS,
          className,
        )}
        {...props}
      >
        {children}
      </select>
    </FieldShell>
  )
}

/** A form-level message: what went wrong and, where possible, what to do next. */
export function FormAlert({
  tone = 'danger',
  children,
}: {
  tone?: 'danger' | 'success' | 'info'
  children: ReactNode
}) {
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={cn('rounded-xl border px-3.5 py-3 text-sm', {
        'border-danger/30 bg-danger-soft text-danger': tone === 'danger',
        'border-success/30 bg-success-soft text-success': tone === 'success',
        'border-info/30 bg-info-soft text-info': tone === 'info',
      })}
    >
      {children}
    </div>
  )
}
