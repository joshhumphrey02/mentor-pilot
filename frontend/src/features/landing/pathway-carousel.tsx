import { HandshakeIcon } from 'lucide-react'

import { CardsCarousel } from '@/components/aceternity/cards-carousel'
import { PATHWAY_STAGES } from '@/features/pathway/stages'
import { PHOTOS } from '@/lib/photos'

// In stage order.
const STAGE_PHOTOS = [
  PHOTOS.stageProblem,
  PHOTOS.stageIdeas,
  PHOTOS.stageQuestion,
  PHOTOS.stageMethod,
  PHOTOS.stageTools,
  PHOTOS.stagePrototype,
  PHOTOS.stageData,
  PHOTOS.stageCommunication,
  PHOTOS.stageExpo,
]
const HANDOFF_STAGE = 'design_prototyping'

/** The nine stages as a row of photo cards to swipe through. */
export function PathwayCarousel() {
  return (
    <CardsCarousel
      label="The nine stages of a project"
      cards={PATHWAY_STAGES.map((stage, index) => ({
        key: stage.key,
        eyebrow: `Stage ${index + 1}`,
        title: stage.title,
        photo: STAGE_PHOTOS[index] ?? PHOTOS.stageProblem,
        badge: stage.key === HANDOFF_STAGE && (
          <p className="inline-flex items-center gap-2 self-start rounded-full bg-spark px-3 py-1 text-sm font-semibold text-spark-foreground">
            <HandshakeIcon aria-hidden="true" className="size-4" />A human mentor joins
          </p>
        ),
      }))}
    />
  )
}
