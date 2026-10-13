import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api/client'
import { cn } from '@/lib/utils'

function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      // A 503 still carries a body describing what is down, so read both.
      const { data, error } = await api.GET('/api/v1/health')
      const health = data ?? error
      if (!health) throw new Error('The server did not respond.')
      return health
    },
    refetchInterval: 30_000,
  })
}

/** A small live indicator that the app can reach the API and its database. */
export function SystemStatus({ className }: { className?: string }) {
  const { data, isPending, isError } = useHealth()

  const state = isPending ? 'checking' : isError || !data ? 'offline' : data.status
  const label = {
    checking: 'Connecting to the mentor…',
    ok: 'Mentor is online',
    degraded: 'Mentor is having trouble',
    offline: "Can't reach the mentor",
  }[state]

  return (
    <p
      role="status"
      className={cn(
        'inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-sm font-medium',
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn('size-2 rounded-full', {
          'animate-pulse bg-muted-foreground': state === 'checking',
          'bg-success': state === 'ok',
          'bg-warning': state === 'degraded',
          'bg-danger': state === 'offline',
        })}
      />
      {label}
    </p>
  )
}
