import { lazy, Suspense } from 'react'

import { cn } from '@/lib/utils'

const MarkdownRenderer = lazy(() => import('./markdown-renderer'))

interface MarkdownBlockProps {
  text: string
  /** Shows a caret after the last character while the mentor is still writing. */
  streaming?: boolean
  className?: string
}

export function MarkdownBlock({ text, streaming, className }: MarkdownBlockProps) {
  return (
    <div className={cn('prose-mentor', streaming && 'is-streaming', className)}>
      {/* Until the renderer has loaded, the raw text is perfectly readable. */}
      <Suspense fallback={<p className="whitespace-pre-wrap">{text}</p>}>
        <MarkdownRenderer text={text} />
      </Suspense>
    </div>
  )
}
