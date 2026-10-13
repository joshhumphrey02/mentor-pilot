import {
  AtomIcon,
  BotIcon,
  CalculatorIcon,
  CodeIcon,
  CogIcon,
  DropletsIcon,
  FlaskConicalIcon,
  HeartPulseIcon,
  LeafIcon,
  type LucideIcon,
  RocketIcon,
  SproutIcon,
  ZapIcon,
} from 'lucide-react'

// Option lists live here, not in the database, so they can grow (other
// countries, university levels) without a migration.

export const PROVINCES = [
  'Western Cape',
  'Eastern Cape',
  'Northern Cape',
  'Free State',
  'Gauteng',
  'KwaZulu-Natal',
  'Limpopo',
  'Mpumalanga',
  'North West',
] as const

export const GRADES = ['8', '9', '10', '11', '12'] as const

export const INTERESTS: { value: string; label: string; icon: LucideIcon }[] = [
  { value: 'robotics', label: 'Robotics', icon: BotIcon },
  { value: 'environment', label: 'Environment', icon: LeafIcon },
  { value: 'health', label: 'Health', icon: HeartPulseIcon },
  { value: 'energy', label: 'Energy', icon: ZapIcon },
  { value: 'agriculture', label: 'Agriculture', icon: SproutIcon },
  { value: 'coding', label: 'Coding', icon: CodeIcon },
  { value: 'water', label: 'Water', icon: DropletsIcon },
  { value: 'space', label: 'Space', icon: RocketIcon },
  { value: 'chemistry', label: 'Chemistry', icon: FlaskConicalIcon },
  { value: 'physics', label: 'Physics', icon: AtomIcon },
  { value: 'engineering', label: 'Engineering', icon: CogIcon },
  { value: 'maths', label: 'Maths', icon: CalculatorIcon },
]

export const LEARNING_STYLES = [
  { value: 'visual', label: 'Show me', description: 'Diagrams, pictures and videos.' },
  { value: 'hands_on', label: 'Let me try', description: 'Building and experimenting.' },
  { value: 'reading', label: 'Let me read', description: 'Clear written explanations.' },
  { value: 'step_by_step', label: 'Walk me through it', description: 'One small step at a time.' },
] as const

export const LANGUAGES = [
  { value: 'en', label: 'English', available: true },
  { value: 'af', label: 'Afrikaans', available: false },
  { value: 'xh', label: 'isiXhosa', available: false },
] as const

const ADULT_AGE = 18

/** Age in whole years on `today`, or null if the date is not valid. */
export function ageFrom(dateOfBirth: string, today = new Date()): number | null {
  const born = new Date(`${dateOfBirth}T00:00:00`)
  if (Number.isNaN(born.getTime())) return null
  const hadBirthday =
    today.getMonth() > born.getMonth() ||
    (today.getMonth() === born.getMonth() && today.getDate() >= born.getDate())
  return today.getFullYear() - born.getFullYear() - (hadBirthday ? 0 : 1)
}

export function isMinor(dateOfBirth: string): boolean {
  const age = ageFrom(dateOfBirth)
  return age !== null && age < ADULT_AGE
}
