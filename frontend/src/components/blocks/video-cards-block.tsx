import { PlayIcon } from 'lucide-react'
import { useState } from 'react'

import { ResponsiveDialog } from '@/components/responsive-dialog'
import type { Schemas } from '@/lib/api/client'

type Video = Schemas['VideoCard']

export function VideoCardsBlock({ block }: { block: Schemas['VideoCardsBlock'] }) {
  const [playing, setPlaying] = useState<Video | null>(null)

  return (
    <>
      <ul aria-label={`Videos about ${block.query}`} className="grid gap-2 sm:grid-cols-2">
        {block.videos.map((video) => (
          <li key={video.video_id}>
            <button
              type="button"
              onClick={() => setPlaying(video)}
              className="flex w-full items-center gap-3 rounded-2xl border bg-card p-2 text-left hover:border-primary"
            >
              <span className="relative w-28 shrink-0 overflow-hidden rounded-xl bg-muted">
                {video.thumbnail_url && (
                  <img
                    src={video.thumbnail_url}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    referrerPolicy="no-referrer"
                    className="aspect-video w-full object-cover"
                  />
                )}
                <span className="absolute inset-0 grid place-items-center bg-black/25">
                  <PlayIcon aria-hidden="true" className="size-6 fill-white text-white" />
                </span>
              </span>
              <span className="min-w-0">
                <span className="line-clamp-2 text-sm font-medium">{video.title}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {video.channel}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>

      <ResponsiveDialog
        open={playing !== null}
        onOpenChange={(open) => !open && setPlaying(null)}
        title={playing?.title ?? 'Video'}
        description={playing?.channel}
      >
        {playing && (
          // The video only loads once a card is tapped, and from YouTube's
          // no-cookie domain, so nothing is fetched or tracked before then.
          <iframe
            title={playing.title}
            src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(playing.video_id)}?autoplay=1&rel=0`}
            allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
            referrerPolicy="strict-origin-when-cross-origin"
            className="aspect-video w-full rounded-xl bg-black"
          />
        )}
      </ResponsiveDialog>
    </>
  )
}
