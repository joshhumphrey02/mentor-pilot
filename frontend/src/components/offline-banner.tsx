import { WifiOffIcon } from 'lucide-react'

import { useOnline } from '@/hooks/use-online'

/** Shown across the top while offline. Recent chats stay readable; sending waits. */
export function OfflineBanner() {
  const online = useOnline()
  if (online) return null
  return (
    <p
      role="status"
      className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-foreground px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))] text-center text-sm font-medium text-background"
    >
      <WifiOffIcon aria-hidden="true" className="size-4 shrink-0" />
      You're offline. You can read your recent chats; sending will work when you're back online.
    </p>
  )
}
