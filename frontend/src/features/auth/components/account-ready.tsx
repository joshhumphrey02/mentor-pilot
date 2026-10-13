import { Link } from '@tanstack/react-router'
import { CircleCheckIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'

/**
 * Shown after signing up when the server confirms accounts itself (it has no
 * email server). Like the "check your inbox" state, it reads the same whether
 * or not the address already had an account.
 */
export function AccountReady({ children }: { children?: ReactNode }) {
  return (
    <div>
      <CircleCheckIcon aria-hidden="true" className="size-8 text-success" />
      <p className="mt-3 font-medium">Log in with the email and password you just chose.</p>
      <p className="mt-1.5 text-sm text-muted-foreground">
        If you already had an account with this email, your old password still applies.
      </p>
      {children && <div className="mt-4">{children}</div>}
      <Button asChild size="touch" className="mt-6 w-full">
        <Link to="/login">Log in</Link>
      </Button>
    </div>
  )
}
