import { Link } from '@tanstack/react-router'
import { ChevronRightIcon } from 'lucide-react'

import { PATHWAY_STAGES, stagePosition } from '@/features/pathway/stages'

import type { Project } from '../api'

const RADIUS = 18
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/** Progress along the nine stages, drawn as a ring around the stage number. */
function StageRing({ stage }: { stage: number }) {
  const total = PATHWAY_STAGES.length
  return (
    <svg viewBox="0 0 44 44" className="size-12 shrink-0" role="img" aria-label={`Stage ${stage} of ${total}`}>
      <circle cx="22" cy="22" r={RADIUS} fill="none" strokeWidth="4" className="stroke-muted" />
      <circle
        cx="22"
        cy="22"
        r={RADIUS}
        fill="none"
        strokeWidth="4"
        strokeLinecap="round"
        className="stroke-primary"
        strokeDasharray={CIRCUMFERENCE}
        strokeDashoffset={CIRCUMFERENCE * (1 - stage / total)}
        transform="rotate(-90 22 22)"
      />
      <text
        x="22"
        y="22"
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-foreground font-heading text-[15px] font-semibold"
      >
        {stage}
      </text>
    </svg>
  )
}

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

function lastActive(iso: string): string {
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60_000)
  if (Math.abs(minutes) < 60) return relative.format(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 24) return relative.format(hours, 'hour')
  return relative.format(Math.round(hours / 24), 'day')
}

export function ProjectCard({ project }: { project: Project }) {
  const stage = stagePosition(project.current_stage)
  return (
    <Link
      to="/project/$projectId"
      params={{ projectId: project.id }}
      className="flex items-center gap-4 rounded-2xl border bg-card p-4 shadow-soft transition-colors hover:border-primary"
    >
      <StageRing stage={stage.number} />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{project.title}</span>
        <span className="block truncate text-sm text-muted-foreground">
          {stage.title} · {lastActive(project.last_activity_at)}
        </span>
      </span>
      <ChevronRightIcon aria-hidden="true" className="size-5 shrink-0 text-muted-foreground" />
    </Link>
  )
}
