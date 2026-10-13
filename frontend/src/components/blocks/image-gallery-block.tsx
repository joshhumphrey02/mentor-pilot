import { ExternalLinkIcon } from 'lucide-react'
import { useState } from 'react'

import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import type { Schemas } from '@/lib/api/client'

type Image = Schemas['GalleryImage']

function credit(image: Image) {
  return [image.author, image.license].filter(Boolean).join(' · ') || 'Wikimedia Commons'
}

/** Photos from Wikimedia Commons, each credited, opening in a lightbox. */
export function ImageGalleryBlock({ block }: { block: Schemas['ImageGalleryBlock'] }) {
  const [active, setActive] = useState<Image | null>(null)

  return (
    <figure>
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {block.images.map((image) => (
          <li key={image.thumbnail_url}>
            <button
              type="button"
              onClick={() => setActive(image)}
              className="group block w-full overflow-hidden rounded-xl border bg-muted text-left"
            >
              <img
                src={image.thumbnail_url}
                alt={image.title}
                loading="lazy"
                decoding="async"
                width={image.width ?? undefined}
                height={image.height ?? undefined}
                // Wikimedia does not need to know which page asked.
                referrerPolicy="no-referrer"
                className="aspect-4/3 w-full object-cover transition-transform group-hover:scale-105"
              />
              <span className="block truncate px-2 py-1.5 text-xs">{image.title}</span>
            </button>
          </li>
        ))}
      </ul>
      <figcaption className="mt-2 text-xs text-muted-foreground">
        Photos of {block.query} from Wikimedia Commons. Tap one for its credit.
      </figcaption>

      <Dialog open={active !== null} onOpenChange={(open) => !open && setActive(null)}>
        <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
          {active && (
            <>
              <DialogTitle className="pr-8">{active.title}</DialogTitle>
              <img
                src={active.thumbnail_url}
                alt={active.title}
                referrerPolicy="no-referrer"
                className="max-h-[60dvh] w-full rounded-xl bg-muted object-contain"
              />
              <DialogDescription>{credit(active)}</DialogDescription>
              {active.source_url && (
                <a
                  href={active.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-primary underline-offset-4 hover:underline"
                >
                  View source and licence
                  <ExternalLinkIcon aria-hidden="true" className="size-4" />
                </a>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </figure>
  )
}
