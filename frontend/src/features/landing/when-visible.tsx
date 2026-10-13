import { type ReactNode, useEffect, useRef, useState } from 'react'

interface WhenVisibleProps {
  children: ReactNode
  /** Reserves the space, so the page does not jump when the content arrives. */
  minHeight: number
}

/**
 * Renders its children only once they are about to scroll into view. Used for
 * the landing page's live demo, so its code is not downloaded by visitors who
 * never scroll that far.
 */
export function WhenVisible({ children, minHeight }: WhenVisibleProps) {
  const holder = useRef<HTMLDivElement>(null)
  // Without IntersectionObserver there is no way to wait, so render at once.
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === 'undefined')

  useEffect(() => {
    const element = holder.current
    if (!element || visible) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setVisible(true)
      },
      { rootMargin: '300px' },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [visible])

  return (
    <div ref={holder} style={visible ? undefined : { minHeight }}>
      {visible ? children : null}
    </div>
  )
}
