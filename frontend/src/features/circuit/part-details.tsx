import { useQuery } from '@tanstack/react-query'

import { ResponsiveDialog } from '@/components/responsive-dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api/client'
import { unwrap } from '@/lib/api/errors'

import { describeHole, type Part } from './geometry'
import { LIBRARY, pinHelp } from './library'
import { componentName } from './steps'

interface PartDetailsProps {
  part: Part | null
  onClose: () => void
  /** Off for the public demo, where there is no session to fetch photos with. */
  photos: boolean
}

/** What a part is, what each leg does, and a photo of the real thing. */
export function PartDetails({ part, onClose, photos }: PartDetailsProps) {
  const photo = useQuery({
    queryKey: ['component-photo', part?.type] as const,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/media/component-photo/{component}', {
          params: { path: { component: part?.type ?? '' } },
        }),
      ),
    enabled: photos && part !== null,
    staleTime: Infinity,
    retry: false,
  })
  const info = part ? LIBRARY[part.type] : null
  const image = photo.data?.image

  return (
    <ResponsiveDialog
      open={part !== null}
      onOpenChange={(open) => !open && onClose()}
      title={part ? componentName(part) : ''}
      description={info?.summary}
    >
      {part && (
        <div className="grid gap-4">
          <dl className="grid gap-2.5">
            {Object.entries(part.pins).map(([pin, hole]) => (
              <div key={pin} className="rounded-xl bg-muted px-3 py-2">
                <dt className="text-sm font-semibold">
                  {pin} <span className="font-normal text-muted-foreground">in {describeHole(hole)}</span>
                </dt>
                <dd className="text-sm">{pinHelp(part.type, pin)}</dd>
              </div>
            ))}
          </dl>

          {photos && photo.isPending && <Skeleton className="aspect-4/3 w-full rounded-xl" />}
          {image && (
            <figure>
              <img
                src={image.thumbnail_url}
                alt={`A real ${LIBRARY[part.type].label}`}
                loading="lazy"
                referrerPolicy="no-referrer"
                className="max-h-56 w-full rounded-xl bg-muted object-contain"
              />
              <figcaption className="mt-1.5 text-xs text-muted-foreground">
                What a real one looks like.{' '}
                {[image.author, image.license].filter(Boolean).join(' · ')}
                {image.source_url && (
                  <>
                    {' · '}
                    <a
                      href={image.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline underline-offset-2"
                    >
                      Wikimedia Commons
                    </a>
                  </>
                )}
              </figcaption>
            </figure>
          )}
        </div>
      )}
    </ResponsiveDialog>
  )
}
