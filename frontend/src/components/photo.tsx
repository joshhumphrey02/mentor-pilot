import { type ComponentProps, useState } from 'react'

import { type Photo as PhotoData, photoSrcSet, photoUrl } from '@/lib/photos'
import { cn } from '@/lib/utils'

interface PhotoProps extends Omit<ComponentProps<'img'>, 'src' | 'srcSet' | 'alt'> {
  photo: PhotoData
  /** How wide the image is shown, as a `sizes` value, so the browser picks the smallest file. */
  sizes: string
  /** For the image a visitor sees first: load it now rather than on scroll. */
  priority?: boolean
  /** When the photo only sets a mood and the text beside it says everything. */
  decorative?: boolean
}

/** An Unsplash photo that fills its box and sharpens into view once it has loaded. */
export function Photo({ photo, sizes, priority, decorative, className, loading, ...props }: PhotoProps) {
  const [loaded, setLoaded] = useState(false)
  return (
    <img
      src={photoUrl(photo, 800)}
      srcSet={photoSrcSet(photo)}
      sizes={sizes}
      alt={decorative ? '' : photo.alt}
      loading={loading ?? (priority ? 'eager' : 'lazy')}
      fetchPriority={priority ? 'high' : undefined}
      decoding="async"
      // A cached image can finish before React attaches the handler.
      ref={(image) => {
        if (image?.complete) setLoaded(true)
      }}
      onLoad={() => setLoaded(true)}
      className={cn(
        'size-full object-cover transition duration-500',
        !loaded && 'scale-[1.02] blur-md',
        className,
      )}
      {...props}
    />
  )
}
