import { useEffect, useState } from 'react'

/**
 * The height of the area actually visible, in pixels, or null if unknown.
 *
 * `100dvh` covers browser toolbars, but on iOS it does not shrink when the
 * on-screen keyboard opens: the page is scrolled instead, which pushes a chat
 * header off the top. Sizing the chat to the visual viewport keeps the header,
 * the latest message and the input all on screen while typing.
 */
export function useVisualViewportHeight(): number | null {
  const [height, setHeight] = useState<number | null>(null)

  useEffect(() => {
    const viewport = window.visualViewport
    if (!viewport) return
    const update = () => {
      setHeight(Math.round(viewport.height))
      // Undo the scroll iOS applies to bring the focused input into view.
      if (viewport.offsetTop > 0) window.scrollTo(0, 0)
    }
    update()
    viewport.addEventListener('resize', update)
    viewport.addEventListener('scroll', update)
    return () => {
      viewport.removeEventListener('resize', update)
      viewport.removeEventListener('scroll', update)
    }
  }, [])

  return height
}
