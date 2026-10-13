import type { Schemas } from '@/lib/api/client'

/** A photo the learner attached. Served only to its owner, by the API. */
export function ImageBlock({ block }: { block: Schemas['ImageBlock'] }) {
  return (
    <img
      src={`/api/v1/attachments/${encodeURIComponent(block.attachment_id)}`}
      alt={block.alt ?? 'Photo from the learner'}
      loading="lazy"
      decoding="async"
      className="max-h-72 max-w-full rounded-2xl border bg-muted object-contain"
    />
  )
}
