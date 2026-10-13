import { Link } from '@tanstack/react-router'
import { ArrowUpRightIcon } from 'lucide-react'
import { Photo } from '@/components/photo'
import type { Photo as PhotoData } from '@/lib/photos'

export interface FocusCard {
  title: string
  caption: string
  photo: PhotoData
  /** Where the card leads. Without it the card is just a picture. */
  to?: '/register' | '/register-mentor'
  action?: string
}

/**
 * Adapted from Aceternity UI's Focus Cards: point at one card and the others
 * step back out of focus. The original only shows a card's title on hover;
 * here it is always visible, because a phone has no hover.
 */
export function FocusCards({ cards }: { cards: FocusCard[] }) {
  return (
    // The focus effect is plain CSS: while any card is hovered, the rest blur.
    <ul className="grid gap-4 md:grid-cols-3 [&:has(li:hover)>li:not(:hover)]:scale-[0.98] [&:has(li:hover)>li:not(:hover)]:blur-[3px]">
      {cards.map((card) => {
        const body = (
          <>
            <Photo
              photo={card.photo}
              sizes="(min-width: 768px) 33vw, 100vw"
              decorative
              className="absolute inset-0 transition-transform duration-700 ease-out group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-neutral-950/85 via-neutral-950/20 to-transparent" />
            <div className="absolute inset-x-0 bottom-0 p-5 text-white">
              <h3 className="text-2xl font-semibold">{card.title}</h3>
              <p className="mt-1 text-sm text-white/85">{card.caption}</p>
              {card.action && (
                <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-spark">
                  {card.action}
                  <ArrowUpRightIcon aria-hidden="true" className="size-4" />
                </span>
              )}
            </div>
          </>
        )
        const className = 'group relative block h-72 overflow-hidden rounded-3xl bg-muted md:h-[26rem]'
        return (
          <li key={card.title} className="transition duration-300 ease-out">
            {card.to ? (
              <Link to={card.to} className={className}>
                {body}
              </Link>
            ) : (
              <div className={className}>{body}</div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
