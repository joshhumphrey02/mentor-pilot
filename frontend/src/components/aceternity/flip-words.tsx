import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'

interface FlipWordsProps {
  words: string[]
  /** Milliseconds each word stays up. */
  duration?: number
  className?: string
}

/**
 * Adapted from Aceternity UI's Flip Words: one word at a time, each letter
 * settling into focus as the last word blurs away. It is hidden from screen
 * readers, so put the full sentence beside it in visually hidden text.
 */
export function FlipWords({ words, duration = 2600, className }: FlipWordsProps) {
  const [index, setIndex] = useState(0)
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    if (reducedMotion || words.length < 2) return
    const timer = setInterval(() => setIndex((current) => (current + 1) % words.length), duration)
    return () => clearInterval(timer)
  }, [reducedMotion, words.length, duration])

  const word = words[index] ?? ''

  return (
    <span aria-hidden="true" className="relative inline-block">
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={word}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -28, x: 24, filter: 'blur(8px)', scale: 1.4 }}
          transition={{ type: 'spring', stiffness: 110, damping: 14 }}
          className={cn('inline-block whitespace-nowrap', className)}
        >
          {[...word].map((letter, position) => (
            <motion.span
              // Letters repeat within a word, so the position is the identity.
              key={`${word}-${position}`}
              initial={{ opacity: 0, y: 10, filter: 'blur(8px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              transition={{ delay: position * 0.04, duration: 0.2 }}
              className="inline-block whitespace-pre"
            >
              {letter}
            </motion.span>
          ))}
        </motion.span>
      </AnimatePresence>
    </span>
  )
}
