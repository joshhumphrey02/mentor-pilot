import { motion, useReducedMotion } from 'motion/react'
import { type ReactNode, useEffect, useState } from 'react'

import { Photo } from '@/components/photo'
import type { Photo as PhotoData } from '@/lib/photos'
import { cn } from '@/lib/utils'

interface ImagesSliderProps {
  photos: PhotoData[]
  children: ReactNode
  className?: string
  /** Milliseconds each photo stays up. */
  interval?: number
}

/**
 * Adapted from Aceternity UI's Images Slider: full-bleed photos that cross-fade
 * behind the content, each drifting slowly while it is up. Unlike the original
 * the content renders at once rather than waiting for every image, and the
 * slideshow stops when a visitor picks a photo or prefers less motion.
 */
export function ImagesSlider({ photos, children, className, interval = 5500 }: ImagesSliderProps) {
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(true)
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    if (!playing || reducedMotion || photos.length < 2) return
    const timer = setInterval(() => setIndex((current) => (current + 1) % photos.length), interval)
    return () => clearInterval(timer)
  }, [playing, reducedMotion, photos.length, interval])

  // Photos are mounted one ahead of the slideshow, so the next is already
  // downloaded when its turn comes and the hero never fades through black.
  const [reached, setReached] = useState(0)
  if (index > reached) setReached(index)

  return (
    <div className={cn('relative isolate overflow-hidden bg-neutral-950', className)}>
      {photos.slice(0, reached + 2).map((item, position) => (
        <motion.div
          key={item.id}
          aria-hidden="true"
          className="absolute inset-0 -z-20"
          initial={false}
          animate={
            position === index
              ? { opacity: 1, scale: [1.12, 1], transition: { opacity: { duration: 1.2 }, scale: { duration: 7, ease: 'easeOut' } } }
              : { opacity: 0, transition: { duration: 1.2 } }
          }
        >
          <Photo photo={item} sizes="100vw" priority={position === 0} loading="eager" decorative />
        </motion.div>
      ))}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-gradient-to-t from-neutral-950 via-neutral-950/55 to-neutral-950/35"
      />

      {children}

      {photos.length > 1 && (
        <div className="absolute right-0 bottom-3 left-0 flex justify-center gap-1">
          {photos.map((item, position) => (
            <button
              key={item.id}
              type="button"
              aria-label={`Show photo ${position + 1} of ${photos.length}`}
              aria-current={position === index ? 'true' : undefined}
              onClick={() => {
                setIndex(position)
                setPlaying(false)
              }}
              className="grid h-8 w-8 place-items-center"
            >
              <span
                className={cn(
                  'h-1.5 rounded-full transition-all duration-300',
                  position === index ? 'w-6 bg-white' : 'w-1.5 bg-white/50',
                )}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
