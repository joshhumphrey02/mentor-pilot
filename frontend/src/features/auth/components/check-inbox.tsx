import { MailCheckIcon } from 'lucide-react'
import type { ReactNode } from 'react'

/** The "we've emailed you" state shared by register, forgot password and resend. */
export function CheckInbox({ email, children }: { email: string; children?: ReactNode }) {
  return (
    <div className="rounded-2xl border bg-card p-5 shadow-soft">
      <MailCheckIcon aria-hidden="true" className="size-8 text-primary" />
      <p className="mt-3 font-medium">
        If <span className="break-all">{email}</span> can be used, a link is on its way.
      </p>
      <p className="mt-1.5 text-sm text-muted-foreground">
        It can take a minute. Check your spam folder too.
      </p>
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}
