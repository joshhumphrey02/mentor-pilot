import { CircleAlertIcon, RotateCwIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { Schemas } from '@/lib/api/client'

interface ErrorBlockProps {
  block: Schemas['ErrorBlock']
  onRetry?: () => void
}

export function ErrorBlock({ block, onRetry }: ErrorBlockProps) {
  return (
    <div role="alert" className="rounded-2xl border border-warning/40 bg-warning-soft p-4">
      <p className="flex items-start gap-2.5">
        <CircleAlertIcon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-warning" />
        <span>{block.text}</span>
      </p>
      {block.retryable && onRetry && (
        <Button variant="outline" size="touch" className="mt-3 bg-background" onClick={onRetry}>
          <RotateCwIcon data-icon="inline-start" />
          Try again
        </Button>
      )}
    </div>
  )
}
