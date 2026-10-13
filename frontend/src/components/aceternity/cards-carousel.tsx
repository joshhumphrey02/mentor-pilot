import { ArrowLeftIcon, ArrowRightIcon } from 'lucide-react'
import { motion } from 'motion/react'
import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'

import { Photo } from '@/components/photo'
import type { Photo as PhotoData } from '@/lib/photos'

export interface CarouselCard {
  key: string
  eyebrow: string
  title: string
  photo: PhotoData
  badge?: ReactNode
}

/**
 * Adapted from Aceternity UI's Apple Cards Carousel: tall photo cards in a row
 * that scrolls sideways, by swipe or with the arrow buttons. The cards do not
 * open into a dialog as the original's do; there is nothing more to read.
 */
export function CardsCarousel({ cards, label }: { cards: CarouselCard[]; label: string }) {
  const track = useRef<HTMLOListElement>(null)
  const [canScroll, setCanScroll] = useState({ back: false, forward: true })

  const measure = useCallback(() => {
    const element = track.current
    if (!element) return
    const { scrollLeft, scrollWidth, clientWidth } = element
    setCanScroll({ back: scrollLeft > 4, forward: scrollLeft < scrollWidth - clientWidth - 4 })
  }, [])

  useEffect(measure, [measure])

  const scrollBy = (direction: 1 | -1) => {
    const element = track.current
    if (!element) return
    element.scrollBy({ left: direction * element.clientWidth * 0.8, behavior: 'smooth' })
  }

  const arrowClass =
    'grid size-11 place-items-center rounded-full border bg-card text-foreground transition-colors hover:bg-secondary disabled:opacity-40'

  return (
    <div>
      <ol
        ref={track}
        aria-label={label}
        onScroll={measure}
        // The side padding lines the first card up with the page's centred column.
        className="flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-smooth px-[max(1rem,calc((100vw-72rem)/2+1rem))] scroll-px-[max(1rem,calc((100vw-72rem)/2+1rem))] pb-2 [scrollbar-width:none] sm:gap-4 [&::-webkit-scrollbar]:hidden"
      >
        {cards.map((card, index) => (
          <motion.li
            key={card.key}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '0px 0px -10% 0px' }}
            transition={{ duration: 0.5, delay: Math.min(index, 4) * 0.08, ease: 'easeOut' }}
            className="group relative h-80 w-56 flex-none snap-start overflow-hidden rounded-3xl bg-muted sm:h-[26rem] sm:w-72"
          >
            <Photo
              photo={card.photo}
              sizes="(min-width: 640px) 288px, 224px"
              decorative
              className="absolute inset-0 transition-transform duration-700 ease-out group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-b from-neutral-950/70 via-neutral-950/10 to-neutral-950/50" />
            <div className="relative flex h-full flex-col justify-between p-5 text-white">
              <div>
                <p className="text-sm font-medium text-white/85">{card.eyebrow}</p>
                <h3 className="mt-1 text-xl font-semibold sm:text-2xl">{card.title}</h3>
              </div>
              {card.badge}
            </div>
          </motion.li>
        ))}
      </ol>

      <div className="mx-auto mt-4 flex max-w-6xl justify-end gap-2 px-safe">
        <button
          type="button"
          aria-label="Scroll back"
          disabled={!canScroll.back}
          onClick={() => scrollBy(-1)}
          className={arrowClass}
        >
          <ArrowLeftIcon aria-hidden="true" className="size-5" />
        </button>
        <button
          type="button"
          aria-label="Scroll forward"
          disabled={!canScroll.forward}
          onClick={() => scrollBy(1)}
          className={arrowClass}
        >
          <ArrowRightIcon aria-hidden="true" className="size-5" />
        </button>
      </div>
    </div>
  )
}
