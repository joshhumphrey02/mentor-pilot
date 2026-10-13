import mermaid from 'mermaid'
import { useEffect, useId, useState } from 'react'

import { resolveTheme, useThemeStore } from '@/stores/theme'

/**
 * Renders Mermaid source to SVG. A separate chunk: Mermaid is large, and only
 * conversations that include a diagram should pay for it.
 */
export default function DiagramRenderer({ source, label }: { source: string; label: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, '')
  const theme = useThemeStore((state) => resolveTheme(state.theme))
  const [svg, setSvg] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let current = true
    mermaid.initialize({
      startOnLoad: false,
      // "strict" makes Mermaid sanitise labels and disables click handlers
      // and embedded HTML: the source comes from a model, so it is untrusted.
      securityLevel: 'strict',
      theme: theme === 'dark' ? 'dark' : 'neutral',
      fontFamily: 'inherit',
    })
    mermaid
      .render(`diagram-${id}`, source)
      .then((result) => {
        if (current) {
          setSvg(result.svg)
          setFailed(false)
        }
      })
      .catch(() => {
        if (current) setFailed(true)
        // Mermaid leaves an error element behind when parsing fails.
        document.getElementById(`ddiagram-${id}`)?.remove()
      })
    return () => {
      current = false
    }
  }, [id, source, theme])

  if (failed) {
    return (
      <div className="rounded-xl bg-muted p-3 text-sm">
        <p className="font-medium">This diagram couldn't be drawn.</p>
        <p className="mt-1 text-muted-foreground">
          Ask your mentor to try again, or to describe it in words.
        </p>
      </div>
    )
  }
  if (!svg) return <div role="status" aria-label="Drawing diagram" className="h-40" />

  return (
    <div
      role="img"
      aria-label={label}
      className="diagram-svg flex justify-center"
      // Safe: produced by Mermaid in strict mode, which sanitises its output.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
