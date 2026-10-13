import { LightbulbIcon, type LucideIcon, ScaleIcon, ShieldAlertIcon, TriangleAlertIcon } from 'lucide-react'

import type { Schemas } from '@/lib/api/client'
import { cn } from '@/lib/utils'

import { MarkdownBlock } from './markdown-block'

type Callout = Schemas['CalloutBlock']

const VARIANTS: Record<
  Callout['variant'],
  { label: string; icon: LucideIcon; className: string; iconClassName: string }
> = {
  tip: {
    label: 'Tip',
    icon: LightbulbIcon,
    className: 'border-info/30 bg-info-soft',
    iconClassName: 'text-info',
  },
  safety: {
    label: 'Safety',
    icon: ShieldAlertIcon,
    className: 'border-danger/40 bg-danger-soft',
    iconClassName: 'text-danger',
  },
  judge_insight: {
    label: 'What judges look for',
    icon: ScaleIcon,
    className: 'border-insight/30 bg-insight-soft',
    iconClassName: 'text-insight',
  },
  common_mistake: {
    label: 'Common mistake',
    icon: TriangleAlertIcon,
    className: 'border-warning/40 bg-warning-soft',
    iconClassName: 'text-warning',
  },
}

export function CalloutBlock({ block }: { block: Callout }) {
  const variant = VARIANTS[block.variant]
  const Icon = variant.icon
  return (
    // role="note" so screen readers announce it as an aside, with its kind.
    <aside role="note" className={cn('rounded-2xl border p-4', variant.className)}>
      <p className={cn('flex items-center gap-2 text-sm font-semibold', variant.iconClassName)}>
        <Icon aria-hidden="true" className="size-4.5" />
        {variant.label}
      </p>
      <MarkdownBlock text={block.text} className="mt-1.5" />
    </aside>
  )
}
